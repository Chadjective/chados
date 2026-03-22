import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useSearchParams, useNavigate, useLocation } from 'react-router-dom';
import { Play, Image, Film, Heart, Search } from 'lucide-react';
import {
  fetchPhotos,
  fetchAlbumPhotos,
  fetchPhotoTimeline,
  searchPhotos,
  getPhotoThumbnailUrl,
} from '../utils/api';
import type { Photo, TimelineEntry, Album } from '../types';
import PhotoLightbox from './PhotoLightbox';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const PAGE_SIZE = 100;

interface MonthGroup {
  year: number;
  month: number;
  photos: Photo[];
}

function groupPhotosByMonth(photos: Photo[]): MonthGroup[] {
  const map = new Map<string, MonthGroup>();
  for (const photo of photos) {
    let year = 0;
    let month = 0;
    if (photo.date_taken) {
      const d = new Date(photo.date_taken);
      year = d.getFullYear();
      month = d.getMonth() + 1;
    }
    const key = `${year}-${month}`;
    if (!map.has(key)) {
      map.set(key, { year, month, photos: [] });
    }
    map.get(key)!.photos.push(photo);
  }
  return Array.from(map.values());
}

export default function PhotoTimeline() {
  const { albumId } = useParams<{ albumId: string }>();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();

  const isVideos = location.pathname === '/photos/videos';
  const isFavorites = location.pathname === '/photos/favorites';
  const isSearch = location.pathname === '/photos/search';
  const searchQuery = searchParams.get('q') || '';

  const [photos, setPhotos] = useState<Photo[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [album, setAlbum] = useState<Album | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [photoSearchInput, setPhotoSearchInput] = useState(searchQuery);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const offset = useRef(0);
  const hasMore = useRef(true);

  // Build a title
  let title = 'Photos';
  if (albumId && album) title = album.name;
  else if (isVideos) title = selectedYear ? `Videos — ${selectedYear}` : 'Videos';
  else if (isFavorites) title = selectedYear ? `Favorites — ${selectedYear}` : 'Favorites';
  else if (isSearch) title = `Search: ${searchQuery}`;
  else if (selectedYear) title = `Photos — ${selectedYear}`;

  const loadPhotos = useCallback(
    async (reset: boolean) => {
      if (reset) {
        offset.current = 0;
        hasMore.current = true;
        setLoading(true);
      } else {
        if (!hasMore.current) return;
        setLoadingMore(true);
      }

      try {
        let result: { photos: Photo[]; total: number };

        if (albumId) {
          const data = await fetchAlbumPhotos(Number(albumId), offset.current, PAGE_SIZE);
          result = { photos: data.photos, total: data.total };
          if (reset) setAlbum(data.album);
        } else if (isSearch && searchQuery) {
          result = await searchPhotos(searchQuery, offset.current, PAGE_SIZE);
        } else {
          result = await fetchPhotos({
            media_type: isVideos ? 'video' : undefined,
            favorite: isFavorites ? true : undefined,
            year: selectedYear || undefined,
            offset: offset.current,
            limit: PAGE_SIZE,
          });
        }

        setTotal(result.total);
        if (reset) {
          setPhotos(result.photos);
        } else {
          setPhotos((prev) => [...prev, ...result.photos]);
        }
        offset.current += result.photos.length;
        hasMore.current = offset.current < result.total;
      } catch (err) {
        console.error('Failed to load photos:', err);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [albumId, isVideos, isFavorites, isSearch, searchQuery, selectedYear]
  );

  // Initial load and reload when filters change
  useEffect(() => {
    loadPhotos(true);
  }, [loadPhotos]);

  // Load timeline for non-album views
  useEffect(() => {
    if (!albumId) {
      fetchPhotoTimeline().then(setTimeline).catch(console.error);
    }
  }, [albumId]);

  // Infinite scroll via IntersectionObserver
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore.current && !loadingMore) {
          loadPhotos(false);
        }
      },
      { rootMargin: '200px' }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [loadPhotos, loadingMore]);

  // Year navigation
  const years = Array.from(new Set(timeline.map((t) => t.year))).sort((a, b) => b - a);

  function jumpToYear(year: number) {
    if (selectedYear === year) {
      // Clicking the same year again clears the filter (back to all photos)
      setSelectedYear(null);
    } else {
      setSelectedYear(year);
      scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  const monthGroups = groupPhotosByMonth(photos);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (photoSearchInput.trim()) {
      navigate(`/photos/search?q=${encodeURIComponent(photoSearchInput.trim())}`);
    }
  }

  return (
    <div className="photo-timeline-container">
      {/* Section navigation */}
      <div className="photo-section-nav">
        <button
          className={`photo-nav-btn ${!isVideos && !isFavorites && !isSearch && !albumId ? 'active' : ''}`}
          onClick={() => navigate('/photos')}
        >
          <Image size={16} /> Timeline
        </button>
        <button
          className={`photo-nav-btn ${isVideos ? 'active' : ''}`}
          onClick={() => navigate('/photos/videos')}
        >
          <Film size={16} /> Videos
        </button>
        <button
          className={`photo-nav-btn ${isFavorites ? 'active' : ''}`}
          onClick={() => navigate('/photos/favorites')}
        >
          <Heart size={16} /> Favorites
        </button>
        <form className="photo-search-form" onSubmit={handleSearch}>
          <Search size={14} />
          <input
            type="text"
            className="photo-search-input"
            placeholder="Search photos..."
            value={photoSearchInput}
            onChange={(e) => setPhotoSearchInput(e.target.value)}
          />
        </form>
      </div>

      <div className="photo-timeline-body">
        {/* Year sidebar */}
        {years.length > 0 && !albumId && (
          <div className="photo-year-nav">
            {selectedYear && (
              <button
                className="photo-year-btn photo-year-all"
                onClick={() => setSelectedYear(null)}
              >
                All
              </button>
            )}
            {years.map((year) => (
              <button
                key={year}
                className={`photo-year-btn${selectedYear === year ? ' active' : ''}`}
                onClick={() => jumpToYear(year)}
              >
                {year}
              </button>
            ))}
          </div>
        )}

        {/* Main grid */}
        <div className="photo-timeline-scroll" ref={scrollRef}>
          <div className="photo-timeline-header">
            <h2>{title}</h2>
            <span className="photo-count">{total.toLocaleString()} items</span>
          </div>

          {loading && (
            <div className="photo-loading">Loading photos...</div>
          )}

          {!loading && photos.length === 0 && (
            <div className="photo-empty">No photos found.</div>
          )}

          {monthGroups.map((group) => {
            const label =
              group.year === 0
                ? 'Unknown date'
                : `${MONTH_NAMES[group.month - 1]} ${group.year}`;
            return (
              <div key={`${group.year}-${group.month}`} data-year={group.year}>
                <div className="photo-month-header">
                  {label}
                  <span className="photo-month-count">{group.photos.length}</span>
                </div>
                <div className="photo-grid">
                  {group.photos.map((photo) => {
                    const globalIndex = photos.indexOf(photo);
                    return (
                      <div
                        key={photo.id}
                        className="photo-thumb"
                        onClick={() => setLightboxIndex(globalIndex)}
                      >
                        <img
                          src={getPhotoThumbnailUrl(photo.id)}
                          alt={photo.title || photo.filename}
                          loading="lazy"
                        />
                        {photo.is_video && (
                          <div className="video-badge">
                            <Play size={18} fill="white" />
                          </div>
                        )}
                        {photo.is_favorite && (
                          <div className="favorite-badge">
                            <Heart size={14} fill="#ff4081" stroke="#ff4081" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {/* Infinite scroll sentinel */}
          <div ref={sentinelRef} style={{ height: 1 }} />
          {loadingMore && (
            <div className="photo-loading">Loading more...</div>
          )}
        </div>
      </div>

      {/* Lightbox */}
      {lightboxIndex !== null && photos[lightboxIndex] && (
        <PhotoLightbox
          photoId={photos[lightboxIndex].id}
          onClose={() => setLightboxIndex(null)}
          onPrev={
            lightboxIndex > 0
              ? () => setLightboxIndex(lightboxIndex - 1)
              : undefined
          }
          onNext={
            lightboxIndex < photos.length - 1
              ? () => setLightboxIndex(lightboxIndex + 1)
              : undefined
          }
          hasPrev={lightboxIndex > 0}
          hasNext={lightboxIndex < photos.length - 1}
        />
      )}
    </div>
  );
}
