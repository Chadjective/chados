import { useEffect, useState, useCallback } from 'react';
import { X, ChevronLeft, ChevronRight, Info } from 'lucide-react';
import { fetchPhoto, getPhotoFullUrl } from '../utils/api';
import type { Photo } from '../types';
import RelatedSidebar from './RelatedSidebar';

interface PhotoLightboxProps {
  photoId: number;
  onClose: () => void;
  onPrev?: () => void;
  onNext?: () => void;
  hasPrev?: boolean;
  hasNext?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Unknown';
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function PhotoLightbox({
  photoId,
  onClose,
  onPrev,
  onNext,
  hasPrev = false,
  hasNext = false,
}: PhotoLightboxProps) {
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [loading, setLoading] = useState(true);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [showInfo, setShowInfo] = useState(false);

  useEffect(() => {
    setLoading(true);
    setImageLoaded(false);
    fetchPhoto(photoId)
      .then(setPhoto)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [photoId]);

  // Prevent body scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, []);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft' && hasPrev && onPrev) onPrev();
      if (e.key === 'ArrowRight' && hasNext && onNext) onNext();
      if (e.key === 'i' || e.key === 'I') setShowInfo((v) => !v);
    },
    [onClose, onPrev, onNext, hasPrev, hasNext]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div className="lightbox" onClick={onClose}>
      <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
        {/* Close button */}
        <button className="lightbox-close" onClick={onClose}>
          <X size={24} />
        </button>

        {/* Info toggle */}
        <button
          className={`lightbox-info-toggle ${showInfo ? 'active' : ''}`}
          onClick={() => setShowInfo((v) => !v)}
        >
          <Info size={20} />
        </button>

        {/* Navigation */}
        {hasPrev && onPrev && (
          <button className="lightbox-nav lightbox-nav-left" onClick={onPrev}>
            <ChevronLeft size={28} />
          </button>
        )}
        {hasNext && onNext && (
          <button className="lightbox-nav lightbox-nav-right" onClick={onNext}>
            <ChevronRight size={28} />
          </button>
        )}

        {/* Main media area */}
        <div className="lightbox-media">
          {(loading || !imageLoaded) && !photo?.is_video && (
            <div className="lightbox-spinner">Loading...</div>
          )}
          {photo && (
            photo.is_video ? (
              <video
                className="lightbox-image"
                src={getPhotoFullUrl(photo.id)}
                controls
                autoPlay
              />
            ) : (
              <img
                className="lightbox-image"
                src={getPhotoFullUrl(photo.id)}
                alt={photo.title || photo.filename}
                onLoad={() => setImageLoaded(true)}
                style={{ display: imageLoaded ? 'block' : 'none' }}
              />
            )
          )}
        </div>

        {/* Info panel */}
        {showInfo && photo && (
          <div className="lightbox-info">
            <h3 className="lightbox-info-title">Details</h3>
            <div className="lightbox-info-rows">
              {photo.title && (
                <div className="lightbox-info-row">
                  <span className="lightbox-info-label">Title</span>
                  <span className="lightbox-info-value">{photo.title}</span>
                </div>
              )}
              {photo.description && (
                <div className="lightbox-info-row">
                  <span className="lightbox-info-label">Description</span>
                  <span className="lightbox-info-value">{photo.description}</span>
                </div>
              )}
              <div className="lightbox-info-row">
                <span className="lightbox-info-label">Date taken</span>
                <span className="lightbox-info-value">{formatDate(photo.date_taken)}</span>
              </div>
              {photo.width && photo.height && (
                <div className="lightbox-info-row">
                  <span className="lightbox-info-label">Dimensions</span>
                  <span className="lightbox-info-value">
                    {photo.width} x {photo.height}
                  </span>
                </div>
              )}
              <div className="lightbox-info-row">
                <span className="lightbox-info-label">File size</span>
                <span className="lightbox-info-value">{formatBytes(photo.size_bytes)}</span>
              </div>
              <div className="lightbox-info-row">
                <span className="lightbox-info-label">Filename</span>
                <span className="lightbox-info-value">{photo.filename}</span>
              </div>
              {(photo.camera_make || photo.camera_model) && (
                <div className="lightbox-info-row">
                  <span className="lightbox-info-label">Camera</span>
                  <span className="lightbox-info-value">
                    {[photo.camera_make, photo.camera_model].filter(Boolean).join(' ')}
                  </span>
                </div>
              )}
              {photo.latitude != null && photo.longitude != null && (
                <div className="lightbox-info-row">
                  <span className="lightbox-info-label">Location</span>
                  <span className="lightbox-info-value">
                    {photo.latitude.toFixed(5)}, {photo.longitude.toFixed(5)}
                  </span>
                </div>
              )}
              {photo.source_album && (
                <div className="lightbox-info-row">
                  <span className="lightbox-info-label">Album</span>
                  <span className="lightbox-info-value">{photo.source_album}</span>
                </div>
              )}
              {photo.is_video && photo.duration_seconds != null && (
                <div className="lightbox-info-row">
                  <span className="lightbox-info-label">Duration</span>
                  <span className="lightbox-info-value">
                    {Math.floor(photo.duration_seconds / 60)}:
                    {String(Math.floor(photo.duration_seconds % 60)).padStart(2, '0')}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Related items sidebar */}
        <RelatedSidebar type="photo" id={photoId} />
      </div>
    </div>
  );
}
