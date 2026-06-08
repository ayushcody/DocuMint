import numpy as np

from workers.extraction import CalibratedConfidence, validate_field_citations


def test_ece_below_target_after_isotonic_calibration() -> None:
    rng = np.random.default_rng(7)
    raw = rng.uniform(0, 1, 1000)
    gt = (raw + rng.normal(0, 0.1, 1000)).clip(0, 1).round()

    calibrator = CalibratedConfidence()
    calibrator.fit(raw, gt)
    calibrated = np.array([calibrator.calibrate(float(score)) for score in raw])

    ece = calibrator.ece(calibrated, gt)

    assert ece < 0.05


def test_validate_field_citations_rejects_missing_citations() -> None:
    try:
        validate_field_citations({"total": {"citations": []}})
    except ValueError as exc:
        assert "total" in str(exc)
    else:
        raise AssertionError("Expected missing citations to be rejected")
