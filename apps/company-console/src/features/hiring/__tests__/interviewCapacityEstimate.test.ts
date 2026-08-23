import { describe, expect, it } from "vitest";

import {
  estimateInterviewCapacity,
  INTERVIEW_CAPACITY_POLICY,
  INTERVIEW_DURATION_MINUTES,
  MAX_GUARANTEED_INTERVIEW_CONCURRENCY,
} from "../interviewCapacityEstimate";

describe("interview capacity estimate", () => {
  it("keeps the product interview duration fixed at 30 minutes", () => {
    expect(INTERVIEW_DURATION_MINUTES).toBe(30);
  });

  it("keeps the highly available API baseline for small interviews", () => {
    expect(estimateInterviewCapacity(4)).toEqual({
      apiTasks: 2,
      workerTasks: 1,
      additionalApiTasks: 0,
      additionalWorkerTasks: 0,
      estimatedIncrementalCostUsd: 0,
      estimatedIncrementalCostKrw: 0,
      apiCapacityWindowMinutes: 55,
      workerCapacityWindowMinutes: 50,
    });
  });

  it("estimates API and Worker reservation floors for 100 people", () => {
    const estimate = estimateInterviewCapacity(100);

    expect(estimate.apiTasks).toBe(5);
    expect(estimate.workerTasks).toBe(5);
    expect(estimate.additionalApiTasks).toBe(3);
    expect(estimate.additionalWorkerTasks).toBe(4);
    expect(estimate.estimatedIncrementalCostUsd).toBeCloseTo(0.345412, 6);
    expect(estimate.estimatedIncrementalCostKrw).toBe(484);
  });

  it("matches the backend reservation policy at the guaranteed 400-person limit", () => {
    const estimate = estimateInterviewCapacity(
      MAX_GUARANTEED_INTERVIEW_CONCURRENCY,
    );

    expect(INTERVIEW_CAPACITY_POLICY).toMatchObject({
      apiBaselineTasks: 2,
      workerBaselineTasks: 1,
      headroomRatio: 1.25,
      safeSessionsPerTask: 25,
      apiPrewarmMinutes: 15,
      apiDrainMinutes: 10,
      workerPrewarmMinutes: 5,
      workerDrainMinutes: 45,
    });
    expect(estimate.apiTasks).toBe(20);
    expect(estimate.workerTasks).toBe(20);
    expect(estimate.additionalApiTasks).toBe(18);
    expect(estimate.additionalWorkerTasks).toBe(19);
  });

  it("falls back to baseline capacity for invalid or negative input", () => {
    expect(estimateInterviewCapacity(Number.NaN).apiTasks).toBe(2);
    expect(estimateInterviewCapacity(Number.NaN).workerTasks).toBe(1);
    expect(estimateInterviewCapacity(-10).estimatedIncrementalCostKrw).toBe(0);
  });
});
