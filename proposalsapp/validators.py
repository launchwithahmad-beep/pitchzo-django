"""Validators for proposalsapp models. Re-exports shared image validator."""
from pitchzo.validators import validate_image_file

# Alias for backward compatibility
validate_portfolio_image = validate_image_file
