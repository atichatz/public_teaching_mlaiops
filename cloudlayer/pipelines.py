"""Lab 5 — compile pipeline/pipeline.yaml into your provider's pipeline service.

This module is Layer 3, so provider SDKs are allowed here and nowhere else. The DAG stays
in YAML; only the translation lives here. That separation is what you argue for or against
in Lab 5 Task 4.

Implement ONE compile function, for your provider.
"""
import os
from pathlib import Path
from typing import Any

import yaml

SPEC = Path(__file__).resolve().parents[1] / "pipeline" / "pipeline.yaml"


def load_spec(path: Path = SPEC) -> dict[str, Any]:
    """Read the neutral DAG and expand ${VAR} references from the environment."""
    raw = path.read_text()
    for key, value in os.environ.items():
        raw = raw.replace(f"${{{key}}}", value)
    return yaml.safe_load(raw)


def compile_aws(spec: dict[str, Any]):
    """SageMaker Pipelines.

    Each step becomes a ProcessingStep or TrainingStep; `condition` becomes a
    ConditionStep. Note that SageMaker's condition steps branch rather than abort, so
    `on_failure: abort` needs a FailStep on the else branch — an asymmetry worth
    mentioning in your Lab 5 write-up.
    """
    raise NotImplementedError("TODO Lab 5: build a sagemaker.workflow.pipeline.Pipeline")


def compile_azure(spec: dict[str, Any]):
    """Azure ML Pipelines.

    Each step becomes a command component; the DAG is expressed as a @pipeline function.
    Conditions use azure.ai.ml.dsl.condition, which is closer to this YAML than the other
    two providers' equivalents.
    """
    raise NotImplementedError("TODO Lab 5: build an azure.ai.ml pipeline job")


def compile_gcp(spec: dict[str, Any]):
    """Vertex AI Pipelines.

    Kubeflow Pipelines underneath: steps become container components, conditions become
    dsl.If blocks. The compiled artifact is a JSON file you submit, so your build step
    produces a file rather than an object — different from the other two.
    """
    try:
        from kfp import compiler, dsl
    except ImportError as exc:  # pragma: no cover - depends on the compiler environment
        raise RuntimeError(
            "KFP is required only to compile the GCP pipeline. "
            "Install kfp==2.17.0 in a separate compiler environment."
        ) from exc

    steps = spec.get("steps", [])
    actual_order = [step.get("name") for step in steps]
    expected_order = [
        "ingest",
        "validate",
        "train",
        "evaluate",
        "register",
        "deploy_staging",
    ]
    if actual_order != expected_order:
        raise ValueError(
            "GCP compiler expects the neutral six-step DAG in order; "
            f"got {actual_order!r}"
        )
    if steps[4].get("condition") != "gate_decision == 'pass'":
        raise ValueError("Registration must be guarded by gate_decision == 'pass'")

    image = os.environ.get("PIPELINE_IMAGE_URI", steps[0]["image"])
    if "${" in image:
        raise RuntimeError(
            "Set PIPELINE_IMAGE_URI to the digest-pinned training image before compiling"
        )
    training_image = image

    @dsl.container_component
    def ingest_component(base_uri: str, run_id: str):
        return dsl.ContainerSpec(
            image=training_image,
            command=["python", "scripts/lab5_pipeline_step.py"],
            args=["ingest", "--base-uri", base_uri, "--run-id", run_id],
        )

    @dsl.container_component
    def validate_component(base_uri: str, run_id: str):
        return dsl.ContainerSpec(
            image=training_image,
            command=["python", "scripts/lab5_pipeline_step.py"],
            args=["validate", "--base-uri", base_uri, "--run-id", run_id],
        )

    @dsl.container_component
    def train_component(base_uri: str, run_id: str, image_tag: str):
        return dsl.ContainerSpec(
            image=training_image,
            command=["python", "scripts/lab5_pipeline_step.py"],
            args=[
                "train",
                "--base-uri",
                base_uri,
                "--run-id",
                run_id,
                "--image-tag",
                image_tag,
            ],
        )

    @dsl.container_component
    def evaluate_component(
        base_uri: str,
        run_id: str,
        incumbent: float,
        decision: dsl.OutputPath(str),
    ):
        return dsl.ContainerSpec(
            image=training_image,
            command=["python", "scripts/lab5_pipeline_step.py"],
            args=[
                "evaluate",
                "--base-uri",
                base_uri,
                "--run-id",
                run_id,
                "--incumbent",
                incumbent,
                "--decision-out",
                decision,
            ],
        )

    @dsl.container_component
    def register_component(
        base_uri: str,
        run_id: str,
        project_id: str,
        region: str,
        model_name: str,
        training_image_uri: str,
        serving_image_uri: str,
        container_registry: str,
        serving_service_account: str,
        model_resource: dsl.OutputPath(str),
    ):
        return dsl.ContainerSpec(
            image=training_image,
            command=["python", "scripts/lab5_pipeline_step.py"],
            args=[
                "register",
                "--base-uri",
                base_uri,
                "--run-id",
                run_id,
                "--project-id",
                project_id,
                "--region",
                region,
                "--model-name",
                model_name,
                "--training-image-uri",
                training_image_uri,
                "--serving-image-uri",
                serving_image_uri,
                "--container-registry",
                container_registry,
                "--serving-service-account",
                serving_service_account,
                "--model-resource-out",
                model_resource,
            ],
        )

    @dsl.container_component
    def deploy_component(
        project_id: str,
        region: str,
        run_id: str,
        model_resource: str,
        endpoint_name: str,
        machine_type: str,
        serving_service_account: str,
        endpoint_resource: dsl.OutputPath(str),
    ):
        return dsl.ContainerSpec(
            image=training_image,
            command=["python", "scripts/lab5_pipeline_step.py"],
            args=[
                "deploy",
                "--project-id",
                project_id,
                "--region",
                region,
                "--run-id",
                run_id,
                "--model-resource",
                model_resource,
                "--endpoint-name",
                endpoint_name,
                "--machine-type",
                machine_type,
                "--serving-service-account",
                serving_service_account,
                "--endpoint-out",
                endpoint_resource,
            ],
        )

    @dsl.pipeline(name=spec["name"])
    def managed_pipeline(
        project_id: str,
        region: str,
        base_uri: str,
        run_id: str,
        image_tag: str,
        serving_image_uri: str,
        container_registry: str,
        serving_service_account: str,
        incumbent: float = 0.845,
        model_name: str = "itcs355-lab5",
        endpoint_name: str = "itcs355-lab5-staging",
        machine_type: str = "n1-standard-2",
    ):
        ingest_task = ingest_component(base_uri=base_uri, run_id=run_id)
        validate_task = validate_component(base_uri=base_uri, run_id=run_id)
        validate_task.after(ingest_task)
        train_task = train_component(
            base_uri=base_uri,
            run_id=run_id,
            image_tag=image_tag,
        )
        train_task.after(validate_task)
        evaluate_task = evaluate_component(
            base_uri=base_uri,
            run_id=run_id,
            incumbent=incumbent,
        )
        evaluate_task.after(train_task)

        with dsl.If(evaluate_task.outputs["decision"] == "pass", name="gate-passed"):
            register_task = register_component(
                base_uri=base_uri,
                run_id=run_id,
                project_id=project_id,
                region=region,
                model_name=model_name,
                training_image_uri=training_image,
                serving_image_uri=serving_image_uri,
                container_registry=container_registry,
                serving_service_account=serving_service_account,
            )
            register_task.after(evaluate_task)
            deploy_task = deploy_component(
                project_id=project_id,
                region=region,
                run_id=run_id,
                model_resource=register_task.outputs["model_resource"],
                endpoint_name=endpoint_name,
                machine_type=machine_type,
                serving_service_account=serving_service_account,
            )
            deploy_task.after(register_task)

        for task in (ingest_task, validate_task, train_task, evaluate_task):
            task.set_caching_options(False)
            task.set_cpu_limit("1")
            task.set_memory_limit("2Gi")

    output = Path(
        os.environ.get(
            "PIPELINE_TEMPLATE_PATH",
            str(SPEC.parent / "lab5-pipeline.json"),
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    compiler.Compiler().compile(
        pipeline_func=managed_pipeline,
        package_path=str(output),
    )
    print(f"compiled Vertex AI pipeline: {output}")
    return output


COMPILERS = {"aws": compile_aws, "azure": compile_azure, "gcp": compile_gcp}


def compile_for(provider: str, spec: dict[str, Any] | None = None):
    spec = spec or load_spec()
    try:
        return COMPILERS[provider.lower()](spec)
    except KeyError:
        raise ValueError(f"No pipeline compiler for {provider!r}") from None
