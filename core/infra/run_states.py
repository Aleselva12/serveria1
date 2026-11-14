"""One lifecycle shared by live runs, delegated runs and PostgreSQL."""
TERMINAL = frozenset({'completed', 'failed', 'cancelled', 'timed_out', 'awaiting_approval', 'interrupted'})
TRANSITIONS = {
    'queued': frozenset({'running', 'cancelled', 'timed_out', 'interrupted'}),
    'running': frozenset({'cancelling', 'completed', 'failed', 'awaiting_approval', 'interrupted'}),
    'cancelling': frozenset({'cancelled', 'timed_out', 'failed', 'interrupted'}),
    # Compatibility for old rows, without automatic resumption.
    'waiting_approval': frozenset({'interrupted', 'cancelled'}),
    **{status: frozenset() for status in TERMINAL},
}

class DurabilityLost(BaseException):
    """Abort the execution chain when its durable record cannot be written."""

class EffectUncertain(BaseException):
    """Stop reasoning after a write/delegation whose effect cannot be confirmed."""
