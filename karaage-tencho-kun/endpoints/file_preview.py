# HTML ファイルプレビューエンドポイント

from collections.abc import Mapping

from dify_plugin import Endpoint
from werkzeug import Request, Response

from tools._file_store import get_file


class FilePreviewEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        file_id = values.get("file_id", "")
        content = get_file(file_id)
        if content is None:
            return Response("File not found or expired", status=404)
        return Response(content, status=200, content_type="text/html; charset=utf-8")
