import type {
  ReviewAnswerQuote,
  ReviewEvidenceContext,
  InterviewStage,
  ReviewQuestionSource,
  ReviewTimelineEntry,
} from "./types";

/**
 * Index the timeline so the report can show what a citation actually points at.
 *
 * Lane D writes an Evidence with the transcript segment id it quoted, and the timeline
 * keys its entries by that same id, so the answer text is already on screen by the time
 * the report renders. Resolving it here instead of over HTTP also keeps answer text out
 * of a second request that would need its own tenant scoping.
 */
export function buildEvidenceContext(
  entries: ReviewTimelineEntry[],
): ReviewEvidenceContext {
  const answersBySegmentId: Record<string, ReviewAnswerQuote> = {};
  const stageBySegmentId: Record<string, InterviewStage> = {};
  const sourcesByCriterionId: Record<string, ReviewQuestionSource[]> = {};
  let pendingStage: InterviewStage | undefined;

  for (const entry of entries) {
    if (entry.type === "question") {
      pendingStage = entry.questionRationale?.interviewStage;
    }
    if (entry.type === "answer" && entry.text) {
      answersBySegmentId[entry.entryId] = {
        text: entry.text,
        startMs: entry.startMs,
        endMs: entry.endMs,
      };
      if (pendingStage) stageBySegmentId[entry.entryId] = pendingStage;
      pendingStage = undefined;
    }

    const rationale = entry.questionRationale;
    if (!rationale) continue;
    const collected = (sourcesByCriterionId[rationale.criterionId] ??= []);
    for (const source of rationale.sourceReferences) {
      // Follow-ups on one criterion keep citing the same chunk; listing it once per
      // question would read as several separate pieces of submitted material.
      if (collected.some((seen) => seen.sourceId === source.sourceId)) continue;
      collected.push(source);
    }
  }

  return { answersBySegmentId, stageBySegmentId, sourcesByCriterionId };
}
