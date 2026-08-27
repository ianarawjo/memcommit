from memcommit.application.operations.ground import model
from memcommit.application.operations.ground.model import records, session


def test_ground_model_facade_reexports_owning_modules() -> None:
    assert model.GroundSession is records.GroundSession
    assert model.GroundItem is records.GroundItem
    assert model.create_ground_session is session.create_ground_session
    assert model.review_ground_item is session.review_ground_item


def test_ground_session_still_round_trips_through_public_facade() -> None:
    ground = model.create_ground_session("package-split")

    assert model.GroundSession.from_dict(ground.to_dict()) == ground
