"""Canvas LTI 1.3 launch — intentionally stubbed for v1.

In production this module wires the tutor into Canvas via PyLTI1p3:
    - Validates the LTI 1.3 JWT id_token signed by Canvas
    - Extracts the learner sub-claim (NRPS / names-and-roles service)
    - Maps it to our internal learner_id
    - Persists the launch context (course_id, resource_link_id) for analytics

For v1 we only need a deterministic placeholder so the rest of the system
(flow, persistence, evals) can be exercised end-to-end. Replace this with a
real PyLTI1p3 implementation before any pilot.

Reference scaffold (do not run as-is):
    from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch
    launch = FlaskMessageLaunch(request, tool_config)
    sub = launch.get_launch_data()['sub']
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanvasLaunchContext:
    """What a real LTI launch would resolve to."""

    learner_id: str
    course_id: str
    resource_link_id: str
    is_stub: bool = True


def launch_from_canvas(id_token: str | None = None) -> CanvasLaunchContext:
    """Stub: returns a deterministic learner context.

    In production this would:
      1. Verify the JWT signature against Canvas's public key
      2. Validate the audience, issuer, nonce, and expiry
      3. Extract `sub`, `https://purl.imsglobal.org/spec/lti/claim/context.id`,
         and `https://purl.imsglobal.org/spec/lti/claim/resource_link.id`

    For v1 we synthesize a stable learner_id from the supplied token (or a
    fixed dev value), so the same browser session reaches the same state.
    """
    if id_token is None:
        logger.warning("canvas_stub: no id_token supplied, using dev fixture")
        return CanvasLaunchContext(
            learner_id="dev-learner-001",
            course_id="dev-course",
            resource_link_id="dev-link",
        )

    digest = hashlib.sha256(id_token.encode("utf-8")).hexdigest()[:12]
    return CanvasLaunchContext(
        learner_id=f"stub-{digest}",
        course_id="stub-course",
        resource_link_id="stub-link",
    )


# TODO(production): replace with real PyLTI1p3 integration. Tracked separately;
# the policy engine, state models, and flow do not depend on any LTI specifics.
