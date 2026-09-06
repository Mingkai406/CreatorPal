import json
import threading

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult


class JsonlExporter(SpanExporter):
    def __init__(self, path):
        self.path, self.lock = path, threading.Lock()

    def export(self, spans):
        with self.lock, self.path.open("a") as output:
            for span in spans:
                output.write(json.dumps(json.loads(span.to_json())) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def make_provider(path):
    provider = TracerProvider(resource=Resource.create({"service.name": "creatorpal-agent"}))
    provider.add_span_processor(SimpleSpanProcessor(JsonlExporter(path)))
    return provider
