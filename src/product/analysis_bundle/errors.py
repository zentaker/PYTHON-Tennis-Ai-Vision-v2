class BundleInputError(Exception):
    """Input descriptor or source is invalid."""


class BundleSchemaError(Exception):
    """A bundle or input fails its JSON schema."""


class BundleIntegrityError(Exception):
    """A checksum, size or fingerprint is invalid."""


class BundlePathError(Exception):
    """A path is unsafe or escapes its permitted root."""


class BundleBuildError(Exception):
    """An atomic bundle build failed."""
