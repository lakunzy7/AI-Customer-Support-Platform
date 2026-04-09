"""OpenTelemetry setup — traces + Prometheus metrics."""

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ai_platform.config import settings


def setup_telemetry(app) -> None:
    """Initialize OpenTelemetry tracing and Prometheus metrics."""
    resource = Resource.create(
        {
            "service.name": settings.app_name,
            "service.version": "0.1.0",
            "deployment.environment": settings.app_env,
        }
    )

    # Traces — OTLP exporter (only if endpoint configured)
    import os

    provider = TracerProvider(resource=resource)
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        exporter = OTLPSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Metrics — Prometheus exporter (serves via prometheus_client registry)
    reader = PrometheusMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    # Auto-instrument FastAPI and httpx
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
