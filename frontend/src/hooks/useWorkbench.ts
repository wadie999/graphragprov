import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  api,
} from "../api/client";

import type {
  CaseSnapshot,
} from "../api/snapshotTypes";

export function useWorkbench() {
  const queryClient =
    useQueryClient();

  const experiments =
    useQuery({
      queryKey: [
        "experiments",
      ],
      queryFn:
        api.experiments,
    });

  const [
    experimentId,
    setExperimentId,
  ] =
    useState<string>();

  const [
    snapshotId,
    setSnapshotId,
  ] =
    useState<string>();

  useEffect(() => {
    if (
      !experimentId
      && experiments.data?.length
    ) {
      setExperimentId(
        experiments.data[0]
          .experiment_id,
      );
    }
  }, [
    experimentId,
    experiments.data,
  ]);

  const cases =
    useQuery({
      queryKey: [
        "cases",
        experimentId,
      ],
      queryFn: () =>
        api.cases(
          experimentId!,
        ),
      enabled:
        Boolean(
          experimentId,
        ),
    });

  useEffect(() => {
    if (!cases.data) {
      return;
    }

    if (
      !cases.data.length
    ) {
      setSnapshotId(
        undefined,
      );

      return;
    }

    if (
      !cases.data.some(
        (item) =>
          item.snapshot_id
          === snapshotId,
      )
    ) {
      setSnapshotId(
        cases.data[0]
          .snapshot_id,
      );
    }
  }, [
    cases.data,
    snapshotId,
  ]);

  const snapshot =
    useQuery({
      queryKey: [
        "snapshot",
        snapshotId,
      ],
      queryFn: () =>
        api.snapshot(
          snapshotId!,
        ),
      enabled:
        Boolean(
          snapshotId,
        ),
    });

  async function refreshExperiments() {
    await queryClient.invalidateQueries({
      queryKey: [
        "experiments",
      ],
    });
  }

  async function refreshCases(
    id = experimentId,
  ) {
    if (!id) {
      return;
    }

    await queryClient.invalidateQueries({
      queryKey: [
        "cases",
        id,
      ],
    });
  }

  function selectSnapshot(
    value: CaseSnapshot,
  ) {
    queryClient.setQueryData(
      [
        "snapshot",
        value.snapshot_id,
      ],
      value,
    );

    setSnapshotId(
      value.snapshot_id,
    );
  }

  return useMemo(
    () => ({
      experiments,
      cases,
      snapshot,

      experimentId,
      snapshotId,

      setExperimentId,
      setSnapshotId,

      refreshExperiments,
      refreshCases,
      selectSnapshot,
    }),
    [
      experiments,
      cases,
      snapshot,
      experimentId,
      snapshotId,
    ],
  );
}