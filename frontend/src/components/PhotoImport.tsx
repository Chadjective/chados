import { useState, useEffect, useCallback, useRef } from 'react';
import { HardDrive, Upload, FolderInput, X, MapPin, CheckCircle2, AlertCircle } from 'lucide-react';
import {
  fetchImportDrives, startFolderImport, fetchImportJobs, cancelImportJob,
} from '../utils/api';
import type { ImportDrive, ImportJob } from '../types';

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(i > 1 ? 1 : 0)} ${sizes[i]}`;
}

const ACTIVE = new Set(['queued', 'running']);

export default function PhotoImport() {
  const [drives, setDrives] = useState<ImportDrive[]>([]);
  const [path, setPath] = useState('');
  const [recursive, setRecursive] = useState(true);
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadJobs = useCallback(async () => {
    try {
      const data = await fetchImportJobs();
      setJobs(data.jobs);
    } catch {
      /* transient — keep last known */
    }
  }, []);

  useEffect(() => {
    fetchImportDrives().then((d) => setDrives(d.drives)).catch(() => setDrives([]));
    loadJobs();
  }, [loadJobs]);

  // Poll while any job is active.
  useEffect(() => {
    const anyActive = jobs.some((j) => ACTIVE.has(j.status));
    if (anyActive && pollRef.current === null) {
      pollRef.current = window.setInterval(loadJobs, 1500);
    } else if (!anyActive && pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [jobs, loadJobs]);

  async function handleStart() {
    if (!path.trim()) return;
    setStarting(true);
    setError(null);
    try {
      await startFolderImport(path.trim(), recursive);
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start import');
    } finally {
      setStarting(false);
    }
  }

  async function handleCancel(jobId: number) {
    try {
      await cancelImportJob(jobId);
      await loadJobs();
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="photo-import">
      <div className="photo-import-header">
        <h2><Upload size={20} /> Import Photos</h2>
        <p className="photo-import-subtitle">
          Add photos from external drives or any folder. Files are <strong>indexed in place</strong> —
          the archive keeps each file's location and a thumbnail, so browsing and search always work;
          full-resolution view needs the drive connected. Duplicates (including across backup drives)
          are skipped automatically.
        </p>
      </div>

      {/* Drive shortcuts */}
      {drives.length > 0 && (
        <div className="photo-import-section">
          <h3>Connected drives</h3>
          <div className="photo-import-drives">
            {drives.map((d) => {
              const pct = d.total_bytes > 0 ? (d.used_bytes / d.total_bytes) * 100 : 0;
              return (
                <button
                  key={d.path}
                  className={`drive-card ${path === d.path ? 'selected' : ''}`}
                  onClick={() => setPath(d.path)}
                  title={`Use ${d.path}`}
                >
                  <div className="drive-card-top">
                    <HardDrive size={18} />
                    <span className="drive-card-name">{d.name}</span>
                  </div>
                  <div className="drive-card-bar">
                    <div className="drive-card-bar-fill" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="drive-card-meta">
                    {formatBytes(d.used_bytes)} used · {formatBytes(d.free_bytes)} free
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Folder path + start */}
      <div className="photo-import-section">
        <h3>Folder to scan</h3>
        <div className="photo-import-form">
          <div className="photo-import-input-wrap">
            <FolderInput size={16} />
            <input
              type="text"
              className="photo-import-input"
              placeholder="/Volumes/easystore/Photos  (or any folder path)"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleStart()}
            />
          </div>
          <label className="photo-import-recursive">
            <input
              type="checkbox"
              checked={recursive}
              onChange={(e) => setRecursive(e.target.checked)}
            />
            Include subfolders
          </label>
          <button
            className="photo-import-start"
            onClick={handleStart}
            disabled={starting || !path.trim()}
          >
            <Upload size={16} /> {starting ? 'Starting…' : 'Start import'}
          </button>
        </div>
        {error && <div className="photo-import-error"><AlertCircle size={14} /> {error}</div>}
      </div>

      {/* Jobs */}
      {jobs.length > 0 && (
        <div className="photo-import-section">
          <h3>Imports</h3>
          <div className="photo-import-jobs">
            {jobs.map((job) => {
              const pct = job.total > 0 ? (job.processed / job.total) * 100 : 0;
              const active = ACTIVE.has(job.status);
              return (
                <div key={job.id} className={`import-job import-job-${job.status}`}>
                  <div className="import-job-head">
                    <span className="import-job-label" title={job.label || ''}>
                      {job.status === 'done' && <CheckCircle2 size={15} className="ij-icon-done" />}
                      {job.status === 'error' && <AlertCircle size={15} className="ij-icon-error" />}
                      {job.label || `Import #${job.id}`}
                    </span>
                    <span className="import-job-status">
                      {active && job.phase === 'scanning' ? 'scanning…' : job.status}
                      {active && (
                        <button className="import-job-cancel" onClick={() => handleCancel(job.id)} title="Cancel">
                          <X size={13} />
                        </button>
                      )}
                    </span>
                  </div>
                  <div className="import-job-bar">
                    <div
                      className="import-job-bar-fill"
                      style={{ width: `${job.phase === 'scanning' ? 100 : pct}%` }}
                    />
                  </div>
                  <div className="import-job-stats">
                    <span>{job.processed.toLocaleString()} / {job.total.toLocaleString()}</span>
                    <span className="ij-imported">{job.imported.toLocaleString()} imported</span>
                    <span className="ij-skipped">{job.skipped.toLocaleString()} skipped</span>
                    {(job.geotagged ?? 0) > 0 && (
                      <span className="ij-geo"><MapPin size={12} /> {job.geotagged?.toLocaleString()} geotagged</span>
                    )}
                    {job.errors > 0 && <span className="ij-errors">{job.errors.toLocaleString()} errors</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
