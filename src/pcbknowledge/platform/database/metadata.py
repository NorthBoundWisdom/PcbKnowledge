"""Import every platform mapping so Alembic sees the complete declarative metadata."""


def load_platform_models() -> None:
    """Load mapping modules for side-effect registration on the shared Base.

    Runtime modules continue to depend on their public interfaces. This import
    hub exists only for migration/autogeneration and schema-consistency tests.
    """

    from pcbknowledge.platform.audit import models as audit_models
    from pcbknowledge.platform.authorization import models as authorization_models
    from pcbknowledge.platform.identity import models as identity_models
    from pcbknowledge.platform.jobs import models as job_models
    from pcbknowledge.platform.outbox import models as outbox_models
    from pcbknowledge.platform.storage import models as storage_models

    assert all(
        module is not None
        for module in (
            audit_models,
            authorization_models,
            identity_models,
            job_models,
            outbox_models,
            storage_models,
        )
    )
