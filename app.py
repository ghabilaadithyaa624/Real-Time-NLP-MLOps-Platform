"""Interactive Gradio Web Application for Real-Time NLP Feedback Classification."""

import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Tuple

import gradio as gr

try:
    from app.inference.predictor import PredictorNotReady, TransformerPredictor
except Exception as err:
    print(f"Notice: TransformerPredictor not available ({err}). Running in standalone mode.")
    PredictorNotReady = RuntimeError
    TransformerPredictor = None

# Determine model directory from environment or default artifacts
DEFAULT_MODEL_DIR = os.getenv("MODEL_PATH", "artifacts/local_model")


def get_predictor() -> Any:
    """Load the platform transformer predictor from environment or fallback path."""
    if TransformerPredictor is None:
        return None
    try:
        predictor = TransformerPredictor.from_environment()
        predictor.warmup()
        return predictor
    except (PredictorNotReady, ValueError, OSError):
        local_path = Path(DEFAULT_MODEL_DIR)
        if local_path.exists():
            try:
                from app.inference.preprocessing import PreprocessingConfig

                config = PreprocessingConfig(max_length=128)
                predictor = TransformerPredictor.from_local(
                    local_path,
                    preprocessing=config,
                    model_version=os.getenv("MODEL_VERSION", "local-v1"),
                )
                predictor.warmup()
                return predictor
            except Exception as inner_exc:
                print(f"Warning: Could not load local model from {local_path}: {inner_exc}")
        return None


predictor = get_predictor()


def classify_feedback(text: str) -> Tuple[Dict[str, float], str, str, Dict[str, Any]]:
    """Classify customer feedback text using the in-memory Transformer model."""
    if not text or not text.strip():
        return (
            {"neutral": 1.0},
            "N/A",
            "Please enter valid feedback text.",
            {"error": "Empty input text"},
        )

    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())

    if predictor is not None:
        try:
            result = predictor.predict(text.strip())
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Compute label confidence distribution for Gradio Label component
            conf = float(result.confidence)
            other_conf = max(0.0, 1.0 - conf)
            if result.prediction.lower() == "positive":
                confidences = {"Positive": conf, "Negative": other_conf}
            else:
                confidences = {"Negative": conf, "Positive": other_conf}

            badge_text = f"✨ **Result:** `{result.prediction.upper()}` (Confidence: {conf * 100:.1f}%)"
            latency_text = f"⚡ **Latency:** `{elapsed_ms:.2f} ms` | **Version:** `{result.model_version}`"

            details = {
                "request_id": request_id,
                "prediction": result.prediction,
                "confidence": round(conf, 4),
                "model_version": result.model_version,
                "latency_ms": round(elapsed_ms, 2),
                "model_source": getattr(predictor, "model_source", "local"),
            }
            return confidences, badge_text, latency_text, details
        except Exception as exc:
            return (
                {"error": 1.0},
                "Error during inference",
                str(exc),
                {"error": str(exc), "request_id": request_id},
            )
    else:
        # Graceful fallback demo response if no model checkpoint has been generated yet
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        lower = text.lower()
        is_pos = any(w in lower for w in ["great", "good", "love", "excellent", "fast", "best", "happy", "amazing"])
        is_neg = any(w in lower for w in ["bad", "terrible", "slow", "horrible", "hate", "worst", "broken", "poor"])

        pred = "Positive" if (is_pos or not is_neg) else "Negative"
        conf = 0.92 if (is_pos or is_neg) else 0.55
        other_conf = 1.0 - conf
        confidences = {pred: conf, ("Negative" if pred == "Positive" else "Positive"): other_conf}

        badge_text = f"✨ **Result:** `{pred.upper()}` (Demo Fallback Mode)"
        latency_text = f"⚡ **Latency:** `{elapsed_ms:.2f} ms` | **Notice:** Live model checkpoint not loaded."
        details = {
            "request_id": request_id,
            "prediction": pred.lower(),
            "confidence": conf,
            "mode": "fallback",
            "latency_ms": round(elapsed_ms, 2),
        }
        return confidences, badge_text, latency_text, details


custom_css = """
.gradio-container {
    max-width: 900px !important;
    margin: auto !important;
}
.header-box {
    text-align: center;
    padding: 24px 16px;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    color: white;
    border-radius: 12px;
    margin-bottom: 20px;
}
.header-box h1 {
    font-size: 2rem;
    margin-bottom: 8px;
    font-weight: 700;
}
.header-box p {
    color: #94a3b8;
    font-size: 1rem;
}
"""

with gr.Blocks(title="Customer Feedback Intelligence") as demo:
    gr.HTML(
        """
        <div class="header-box">
            <h1>🚀 Real-Time NLP Feedback Intelligence</h1>
            <p>High-performance, low-latency customer feedback classification powered by Transformers and MLOps.</p>
        </div>
        """
    )

    with gr.Row():
        with gr.Column(scale=3):
            input_text = gr.Textbox(
                label="Customer Feedback / Review",
                placeholder="Type or paste customer feedback here (e.g., 'The platform was intuitive and fast!')",
                lines=4,
            )
            with gr.Row():
                submit_btn = gr.Button("⚡ Classify Sentiment", variant="primary")
                clear_btn = gr.ClearButton(components=[input_text])

            gr.Examples(
                examples=[
                    ["The support team resolved my issue in less than five minutes. Outstanding service!"],
                    ["The API latency is unacceptable and the dashboard keeps freezing during peak hours."],
                    ["The updated user interface is clean, modern, and very easy to navigate."],
                    ["I am thoroughly disappointed with the recent billing discrepancies and delays."],
                ],
                inputs=input_text,
                label="Quick Examples",
            )

        with gr.Column(scale=2):
            label_output = gr.Label(label="Sentiment Distribution", num_top_classes=2)
            badge_markdown = gr.Markdown("### Awaiting input...")
            latency_markdown = gr.Markdown()
            with gr.Accordion("Technical Metadata & Payload", open=False):
                json_output = gr.JSON(label="Inference Details")

    submit_btn.click(
        fn=classify_feedback,
        inputs=[input_text],
        outputs=[label_output, badge_markdown, latency_markdown, json_output],
    )
    input_text.submit(
        fn=classify_feedback,
        inputs=[input_text],
        outputs=[label_output, badge_markdown, latency_markdown, json_output],
    )

if __name__ == "__main__":
    port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    host = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
    print(f"Starting Gradio server at http://{host}:{port}")
    demo.launch(server_name=host, server_port=port, share=False)
