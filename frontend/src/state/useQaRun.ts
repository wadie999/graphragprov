import { useCallback, useEffect, useReducer, useRef } from "react";

import { runQaStream } from "../api/qaStream";
import type { QaRunConfig, QaRunState } from "../domain/qa";
import {
  initialQaRunState,
  qaRunReducer,
} from "./qaRunReducer";

export interface QaRunController {
  state: QaRunState;
  start: (
    experimentId: string,
    caseId: string,
    config: QaRunConfig,
  ) => Promise<void>;
  cancel: () => void;
  reset: () => void;
}

export function useQaRun(): QaRunController {
  const [state, dispatch] = useReducer(
    qaRunReducer,
    initialQaRunState,
  );
  const abortControllerRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    dispatch({ type: "CANCELLED" });
  }, []);

  const start = useCallback(
    async (
      experimentId: string,
      caseId: string,
      config: QaRunConfig,
    ): Promise<void> => {
      abortControllerRef.current?.abort();

      const controller = new AbortController();
      abortControllerRef.current = controller;

      dispatch({ type: "START", config });

      try {
        for await (const event of runQaStream(
          experimentId,
          caseId,
          config,
          controller.signal,
        )) {
          dispatch({ type: "EVENT", event });
        }

        dispatch({ type: "STREAM_ENDED" });
      } catch (reason: unknown) {
        if (controller.signal.aborted) {
          dispatch({ type: "CANCELLED" });
          return;
        }

        dispatch({
          type: "EVENT",
          event: {
            type: "run.failed",
            error: {
              error_type:
                reason instanceof Error
                  ? reason.name
                  : "UnknownError",
              message:
                reason instanceof Error
                  ? reason.message
                  : String(reason),
            },
          },
        });
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
      }
    },
    [],
  );

  const reset = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    dispatch({ type: "RESET" });
  }, []);

  useEffect(
    () => () => {
      abortControllerRef.current?.abort();
    },
    [],
  );

  return {
    state,
    start,
    cancel,
    reset,
  };
}
