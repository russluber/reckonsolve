"""Type-aware aggregate filter validation shared by both supported models."""

import pytest

from reckonsolve.application.errors import ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database


def test_application_rejects_unit_filter_outside_numeric_view(tmp_path):
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database)
    with pytest.raises(ValidationError) as error_info:
        operations.get_forecast_analytics(unit="days")
    assert error_info.value.field == "unit"
    database.close()
