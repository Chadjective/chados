import type { AttachmentInfo } from "../types";
import { formatFileSize } from "../utils/format";
import { getAttachmentUrl, getAttachmentPreviewUrl } from "../utils/api";

interface AttachmentViewerProps {
  attachments: AttachmentInfo[];
}

function getFileIcon(contentType: string | null): string {
  if (!contentType) return "📄";
  if (contentType.startsWith("image/")) return "🖼️";
  if (contentType === "application/pdf") return "📕";
  if (contentType.startsWith("text/")) return "📄";
  if (contentType.includes("spreadsheet") || contentType.includes("excel")) return "📊";
  if (contentType.includes("document") || contentType.includes("word")) return "📝";
  if (contentType.includes("zip") || contentType.includes("compressed")) return "📦";
  if (contentType.startsWith("audio/")) return "🎵";
  if (contentType.startsWith("video/")) return "🎬";
  return "📎";
}

function isPreviewable(contentType: string | null): boolean {
  if (!contentType) return false;
  return (
    contentType.startsWith("image/") ||
    contentType === "application/pdf" ||
    contentType.startsWith("text/")
  );
}

export default function AttachmentViewer({ attachments }: AttachmentViewerProps) {
  if (attachments.length === 0) return null;

  return (
    <div className="attachments">
      <div className="attachments-header">
        📎 {attachments.length} attachment{attachments.length !== 1 ? "s" : ""}
      </div>
      <div className="attachments-list">
        {attachments.map((att) => (
          <div key={att.id} className="attachment-item">
            <span className="attachment-icon">{getFileIcon(att.content_type)}</span>
            <div className="attachment-info">
              <span className="attachment-name">{att.filename || "unnamed"}</span>
              <span className="attachment-size">{formatFileSize(att.size_bytes)}</span>
            </div>
            <div className="attachment-actions">
              {isPreviewable(att.content_type) && (
                <a
                  href={getAttachmentPreviewUrl(att.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="attachment-btn"
                  title="Preview"
                >
                  👁️
                </a>
              )}
              <a
                href={getAttachmentUrl(att.id)}
                download
                className="attachment-btn"
                title="Download"
              >
                ⬇️
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
