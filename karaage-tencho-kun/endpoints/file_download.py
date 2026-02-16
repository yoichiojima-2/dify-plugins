# File download endpoint
# Serves files stored in the in-memory file store

from collections.abc import Mapping

from werkzeug import Request, Response

from dify_plugin import Endpoint

from data.file_store import get_file


class FileDownloadEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        file_id = values.get("file_id", "")
        entry = get_file(file_id)

        if entry is None:
            return Response(
                "File not found or expired",
                status=404,
                content_type="text/plain; charset=utf-8",
            )

        return Response(
            entry["content"],
            status=200,
            content_type=entry["mime_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{entry["filename"]}"',
            },
        )
