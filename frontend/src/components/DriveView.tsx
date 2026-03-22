import { useEffect, useState, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Folder, File, FileText, FileImage, FileCode, FileVideo, FileAudio,
  ChevronRight, Search, X, ArrowLeft, Home,
} from 'lucide-react';
import { fetchDriveFiles, fetchDriveFile, fetchDriveFolders, searchDrive, getDriveFilePreviewUrl } from '../utils/api';
import type { DriveFile } from '../types';

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString([], {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

function getFileIcon(file: DriveFile) {
  if (file.is_folder) return <Folder size={18} />;
  const mime = file.mime_type || '';
  if (mime.startsWith('image/')) return <FileImage size={18} />;
  if (mime.startsWith('video/')) return <FileVideo size={18} />;
  if (mime.startsWith('audio/')) return <FileAudio size={18} />;
  if (mime.startsWith('text/') || mime.includes('json') || mime.includes('xml') || mime.includes('javascript'))
    return <FileCode size={18} />;
  if (mime.includes('pdf') || mime.includes('document') || mime.includes('word'))
    return <FileText size={18} />;
  return <File size={18} />;
}

export default function DriveView() {
  const navigate = useNavigate();
  const params = useParams<{ '*': string }>();
  const currentPath = params['*'] || '';

  const [files, setFiles] = useState<DriveFile[]>([]);
  const [folders, setFolders] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<DriveFile[] | null>(null);
  const [previewFile, setPreviewFile] = useState<DriveFile | null>(null);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    fetchDriveFolders().then(setFolders).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    setSearchResults(null);
    fetchDriveFiles({ path: currentPath, limit: 500 })
      .then((res) => {
        setFiles(res.files);
        setTotal(res.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [currentPath]);

  function handleSearch() {
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }
    searchDrive(query.trim(), 0, 100)
      .then((res) => setSearchResults(res.files))
      .catch(console.error);
  }

  function handleFileClick(file: DriveFile) {
    if (file.is_folder) {
      navigate(`/drive/folder/${encodeURIComponent(file.path)}`);
    } else {
      openPreview(file);
    }
  }

  function openPreview(file: DriveFile) {
    setPreviewFile(file);
    setPreviewContent(null);
    const mime = file.mime_type || '';
    if (
      mime.startsWith('text/') ||
      mime.includes('json') ||
      mime.includes('xml') ||
      mime.includes('javascript') ||
      mime.includes('html')
    ) {
      setPreviewLoading(true);
      fetch(getDriveFilePreviewUrl(file.id))
        .then((r) => r.text())
        .then(setPreviewContent)
        .catch(() => setPreviewContent('Unable to load preview'))
        .finally(() => setPreviewLoading(false));
    } else if (file.extracted_text) {
      setPreviewContent(file.extracted_text);
    }
  }

  const breadcrumbs = useMemo(() => {
    if (!currentPath) return [];
    const parts = currentPath.split('/').filter(Boolean);
    return parts.map((part, i) => ({
      label: part,
      path: parts.slice(0, i + 1).join('/'),
    }));
  }, [currentPath]);

  const folderTree = useMemo(() => {
    // Get root-level folders (paths with no '/')
    const roots = folders.filter((f) => !f.includes('/'));
    return roots.sort((a, b) => a.localeCompare(b));
  }, [folders]);

  const displayFiles = searchResults !== null ? searchResults : files;
  const sortedFiles = useMemo(() => {
    return [...displayFiles].sort((a, b) => {
      if (a.is_folder && !b.is_folder) return -1;
      if (!a.is_folder && b.is_folder) return 1;
      return a.filename.localeCompare(b.filename);
    });
  }, [displayFiles]);

  return (
    <div className="drive-container">
      <div className="drive-sidebar">
        <div className="drive-sidebar-header">
          <h3>Folders</h3>
        </div>
        <div className="drive-folder-tree">
          <button
            className={`drive-folder-item ${currentPath === '' ? 'active' : ''}`}
            onClick={() => navigate('/drive')}
          >
            <Home size={16} />
            <span>My Drive</span>
          </button>
          {folderTree.map((folder) => (
            <button
              key={folder}
              className={`drive-folder-item ${currentPath === folder ? 'active' : ''}`}
              onClick={() => navigate(`/drive/folder/${encodeURIComponent(folder)}`)}
            >
              <Folder size={16} />
              <span>{folder}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="drive-main">
        <div className="drive-toolbar">
          <div className="drive-breadcrumbs">
            <button className="drive-breadcrumb" onClick={() => navigate('/drive')}>
              My Drive
            </button>
            {breadcrumbs.map((crumb) => (
              <span key={crumb.path} className="drive-breadcrumb-sep">
                <ChevronRight size={14} />
                <button
                  className="drive-breadcrumb"
                  onClick={() => navigate(`/drive/folder/${encodeURIComponent(crumb.path)}`)}
                >
                  {crumb.label}
                </button>
              </span>
            ))}
          </div>
          <div className="drive-search-wrapper">
            <Search size={14} />
            <input
              type="text"
              placeholder="Search files..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="drive-search-input"
            />
            {query && (
              <button className="search-clear" onClick={() => { setQuery(''); setSearchResults(null); }}>
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        <div className="drive-content">
          <div className={`drive-file-list ${previewFile ? 'with-preview' : ''}`}>
            {loading ? (
              <div className="drive-loading">Loading files...</div>
            ) : sortedFiles.length === 0 ? (
              <div className="drive-empty">
                {searchResults !== null ? 'No files match your search' : 'This folder is empty'}
              </div>
            ) : (
              <table className="drive-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Modified</th>
                    <th>Size</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedFiles.map((file) => (
                    <tr
                      key={file.id}
                      className={`drive-file-row ${previewFile?.id === file.id ? 'selected' : ''}`}
                      onClick={() => handleFileClick(file)}
                    >
                      <td className="drive-file-name">
                        <span className="drive-file-icon">{getFileIcon(file)}</span>
                        {file.filename}
                      </td>
                      <td className="drive-file-date">{formatDate(file.modified_time)}</td>
                      <td className="drive-file-size">
                        {file.is_folder ? '--' : formatSize(file.size_bytes)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {previewFile && (
            <div className="drive-preview">
              <div className="drive-preview-header">
                <h3>{previewFile.filename}</h3>
                <button className="drive-preview-close" onClick={() => setPreviewFile(null)}>
                  <X size={16} />
                </button>
              </div>
              <div className="drive-preview-body">
                {previewFile.mime_type?.startsWith('image/') ? (
                  <img
                    src={getDriveFilePreviewUrl(previewFile.id)}
                    alt={previewFile.filename}
                    className="drive-preview-image"
                  />
                ) : previewFile.mime_type?.includes('html') && previewContent ? (
                  <iframe
                    srcDoc={previewContent}
                    title={previewFile.filename}
                    className="drive-preview-iframe"
                    sandbox=""
                  />
                ) : previewLoading ? (
                  <div className="drive-preview-loading">Loading preview...</div>
                ) : previewContent ? (
                  <pre className="drive-preview-text">{previewContent}</pre>
                ) : previewFile.extracted_text ? (
                  <pre className="drive-preview-text">{previewFile.extracted_text}</pre>
                ) : (
                  <div className="drive-preview-none">
                    <File size={48} />
                    <p>No preview available</p>
                    <p className="drive-preview-meta">
                      {previewFile.mime_type} | {formatSize(previewFile.size_bytes)}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
