from training.config import load_experiment_config


def test_mlflow_configuration_is_explicit_and_disabled_by_default():
    config = load_experiment_config("training/config.yaml")

    assert config.mlflow.enabled is False
    assert config.mlflow.tracking_uri == "file:./mlruns"
    assert config.mlflow.experiment_name == "customer-feedback-classifier"
    assert config.mlflow.registered_model_name == "customer-feedback-classifier"
