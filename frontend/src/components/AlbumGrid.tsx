import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderOpen } from 'lucide-react';
import { fetchAlbums, getPhotoThumbnailUrl } from '../utils/api';
import type { Album } from '../types';

export default function AlbumGrid() {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchAlbums()
      .then(setAlbums)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="album-grid-container">
      <div className="photo-section-nav">
        <button className="photo-nav-btn" onClick={() => navigate('/photos')}>
          Timeline
        </button>
        <button className="photo-nav-btn active">
          <FolderOpen size={16} /> Albums
        </button>
      </div>

      <div className="album-grid-body">
        <h2 className="album-grid-title">Albums</h2>
        <span className="photo-count">{albums.length} albums</span>

        {loading && <div className="photo-loading">Loading albums...</div>}

        {!loading && albums.length === 0 && (
          <div className="photo-empty">No albums found.</div>
        )}

        <div className="album-grid">
          {albums.map((album) => (
            <div
              key={album.id}
              className="album-card"
              onClick={() => navigate(`/photos/album/${album.id}`)}
            >
              <div className="album-card-cover">
                {album.cover_photo_id && album.has_cover_thumbnail ? (
                  <img
                    src={getPhotoThumbnailUrl(album.cover_photo_id)}
                    alt={album.name}
                    loading="lazy"
                  />
                ) : (
                  <div className="album-card-placeholder">
                    <FolderOpen size={48} />
                  </div>
                )}
              </div>
              <div className="album-card-info">
                <div className="album-card-name">{album.name}</div>
                <div className="album-card-count">
                  {album.photo_count} item{album.photo_count !== 1 ? 's' : ''}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
