export const INTERVIEW_DURATION_MINUTES = 30;
export const MAX_GUARANTEED_INTERVIEW_CONCURRENCY = 400;

export const INTERVIEW_CAPACITY_POLICY = Object.freeze({
  apiBaselineTasks: 2,
  apiPrewarmMinutes: 15,
  apiDrainMinutes: 10,
  workerBaselineTasks: 1,
  workerPrewarmMinutes: 5,
  workerDrainMinutes: 45,
  headroomRatio: 1.25,
  safeSessionsPerTask: 25,
});

const FARGATE_TASK_USD_PER_HOUR = 0.05678;
const PRESENTATION_USD_TO_KRW = 1_400;

export type InterviewCapacityEstimate = Readonly<{
  apiTasks: number;
  workerTasks: number;
  additionalApiTasks: number;
  additionalWorkerTasks: number;
  estimatedIncrementalCostUsd: number;
  estimatedIncrementalCostKrw: number;
  apiCapacityWindowMinutes: number;
  workerCapacityWindowMinutes: number;
}>;

/**
 * Reservation-floor estimate. Queue pressure may add more Worker tasks, so this is presented as
 * an estimate rather than a quote; the same coefficients are defaults in the backend planner.
 */
export function estimateInterviewCapacity(
  requestedConcurrency: number,
): InterviewCapacityEstimate {
  const concurrency = Number.isFinite(requestedConcurrency)
    ? Math.max(0, Math.floor(requestedConcurrency))
    : 0;
  const apiTasks = Math.max(
    INTERVIEW_CAPACITY_POLICY.apiBaselineTasks,
    Math.ceil(
      (concurrency * INTERVIEW_CAPACITY_POLICY.headroomRatio) /
        INTERVIEW_CAPACITY_POLICY.safeSessionsPerTask,
    ),
  );
  const additionalApiTasks = Math.max(
    0,
    apiTasks - INTERVIEW_CAPACITY_POLICY.apiBaselineTasks,
  );
  const workerTasks = Math.max(
    INTERVIEW_CAPACITY_POLICY.workerBaselineTasks,
    Math.ceil(
      (concurrency * INTERVIEW_CAPACITY_POLICY.headroomRatio) /
        INTERVIEW_CAPACITY_POLICY.safeSessionsPerTask,
    ),
  );
  const additionalWorkerTasks = Math.max(
    0,
    workerTasks - INTERVIEW_CAPACITY_POLICY.workerBaselineTasks,
  );
  const apiCapacityWindowMinutes =
    INTERVIEW_CAPACITY_POLICY.apiPrewarmMinutes +
    INTERVIEW_DURATION_MINUTES +
    INTERVIEW_CAPACITY_POLICY.apiDrainMinutes;
  const workerCapacityWindowMinutes =
    INTERVIEW_CAPACITY_POLICY.workerPrewarmMinutes +
    INTERVIEW_CAPACITY_POLICY.workerDrainMinutes;
  const estimatedIncrementalCostUsd =
    (additionalApiTasks * (apiCapacityWindowMinutes / 60) +
      additionalWorkerTasks * (workerCapacityWindowMinutes / 60)) *
    FARGATE_TASK_USD_PER_HOUR;

  return {
    apiTasks,
    workerTasks,
    additionalApiTasks,
    additionalWorkerTasks,
    estimatedIncrementalCostUsd,
    estimatedIncrementalCostKrw: Math.round(
      estimatedIncrementalCostUsd * PRESENTATION_USD_TO_KRW,
    ),
    apiCapacityWindowMinutes,
    workerCapacityWindowMinutes,
  };
}

export function formatEstimatedKrw(value: number): string {
  return new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: 0,
  }).format(Math.max(0, Math.round(value)));
}
