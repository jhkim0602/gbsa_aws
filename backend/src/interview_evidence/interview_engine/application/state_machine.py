from interview_evidence.interview_engine.domain.session import (
    InterviewSession,
    InterviewSessionState,
)


class StaleSessionSequence(ValueError):
    def __init__(self, current: InterviewSession) -> None:
        super().__init__("session sequence is stale")
        self.current = current


class SessionStateMachine:
    def transition(
        self,
        session: InterviewSession,
        *,
        expected_sequence: int,
        target: InterviewSessionState,
    ) -> InterviewSession:
        if expected_sequence != session.session_sequence:
            raise StaleSessionSequence(session)
        return session.transition(target)
