import { useEffect, useState } from "react";

import {
  listExperimentCases,
  listExperiments,
  loadCaseReference,
} from "../api/experiments";
import type {
  ExperimentCaseReference,
  ExperimentCaseSummary,
  ExperimentSummary,
} from "../domain/experiment";

export interface ExperimentBrowserState {
  experiments: ExperimentSummary[];
  cases: ExperimentCaseSummary[];
  reference: ExperimentCaseReference | null;
  selectedExperimentId: string;
  selectedCaseId: string;
  loading: boolean;
  error: string | null;
  selectExperiment: (experimentId: string) => void;
  selectCase: (caseId: string) => void;
  reloadReference: () => void;
}

export function useExperimentBrowser(): ExperimentBrowserState {
  const [experiments, setExperiments] = useState<
    ExperimentSummary[]
  >([]);

  const [cases, setCases] = useState<
    ExperimentCaseSummary[]
  >([]);

  const [reference, setReference] =
    useState<ExperimentCaseReference | null>(null);

  const [
    selectedExperimentId,
    setSelectedExperimentId,
  ] = useState("");

  const [selectedCaseId, setSelectedCaseId] =
    useState("");

  const [referenceVersion, setReferenceVersion] =
    useState(0);

  const [experimentsLoading, setExperimentsLoading] =
    useState(false);

  const [casesLoading, setCasesLoading] =
    useState(false);

  const [referenceLoading, setReferenceLoading] =
    useState(false);

  const [error, setError] = useState<string | null>(
    null,
  );

  useEffect(() => {
    let active = true;

    setExperimentsLoading(true);

    void listExperiments()
      .then((response) => {
        if (!active) {
          return;
        }

        setExperiments(response.items);

        setSelectedExperimentId((current) =>
          response.items.some(
            (experiment) =>
              experiment.experiment_id === current,
          )
            ? current
            : (response.items[0]?.experiment_id ?? ""),
        );

        setError(null);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(errorMessage(reason));
        }
      })
      .finally(() => {
        if (active) {
          setExperimentsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedExperimentId) {
      setCases([]);
      setSelectedCaseId("");
      setCasesLoading(false);
      return;
    }

    let active = true;

    setCasesLoading(true);

    void listExperimentCases(selectedExperimentId)
      .then((response) => {
        if (!active) {
          return;
        }

        setCases(response.items);

        setSelectedCaseId((current) =>
          response.items.some(
            (item) => item.case_id === current,
          )
            ? current
            : (response.items[0]?.case_id ?? ""),
        );

        setError(null);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(errorMessage(reason));
        }
      })
      .finally(() => {
        if (active) {
          setCasesLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedExperimentId]);

  useEffect(() => {
    if (!selectedExperimentId || !selectedCaseId) {
      setReference(null);
      setReferenceLoading(false);
      return;
    }

    let active = true;

    setReferenceLoading(true);

    void loadCaseReference(
      selectedExperimentId,
      selectedCaseId,
    )
      .then((value) => {
        if (!active) {
          return;
        }

        setReference(value);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) {
          return;
        }

        setReference(null);
        setError(errorMessage(reason));
      })
      .finally(() => {
        if (active) {
          setReferenceLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [
    selectedExperimentId,
    selectedCaseId,
    referenceVersion,
  ]);

  return {
    experiments,
    cases,
    reference,
    selectedExperimentId,
    selectedCaseId,
    loading:
      experimentsLoading ||
      casesLoading ||
      referenceLoading,
    error,
    selectExperiment: setSelectedExperimentId,
    selectCase: setSelectedCaseId,
    reloadReference: () =>
      setReferenceVersion((value) => value + 1),
  };
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error
    ? reason.message
    : String(reason);
}