import { useState, useEffect, useCallback, useRef, type RefObject } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Virtuoso, type VirtuosoHandle } from 'react-virtuoso';
import type { EmailSummary } from '../types';
import { fetchEmails, searchEmails } from '../utils/api';
import EmailRow from './EmailRow';
import ActionToolbar from './ActionToolbar';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useSelection } from '../hooks/useSelection';

const PAGE_SIZE = 50;

interface EmailListProps {
  searchInputRef: RefObject<HTMLInputElement | null>;
}

export default function EmailList({ searchInputRef }: EmailListProps) {
  const params = useParams<{ name: string }>();
  const [searchParams] = useSearchParams();
  const label = params.name || '';
  const query = searchParams.get('q') || '';

  const [emails, setEmails] = useState<EmailSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const fetchIdRef = useRef(0);
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const selection = useSelection();

  const loadEmails = useCallback(
    async (offset: number, append: boolean) => {
      const id = ++fetchIdRef.current;
      setLoading(true);
      try {
        let result;
        if (query) {
          result = await searchEmails(query, offset, PAGE_SIZE);
        } else {
          result = await fetchEmails({
            label: label || undefined,
            offset,
            limit: PAGE_SIZE,
          });
        }
        if (id !== fetchIdRef.current) return;
        if (append) {
          setEmails((prev) => [...prev, ...result.emails]);
        } else {
          setEmails(result.emails);
        }
        setTotal(result.total);
      } catch (err) {
        console.error('Failed to fetch emails:', err);
      } finally {
        if (id === fetchIdRef.current) {
          setLoading(false);
          setInitialLoading(false);
        }
      }
    },
    [label, query]
  );

  // Reset on label/query change
  useEffect(() => {
    setEmails([]);
    setTotal(0);
    setSelectedIndex(-1);
    setInitialLoading(true);
    selection.clearSelection();
    loadEmails(0, false);
  }, [loadEmails]);

  // Scroll selected index into view
  useEffect(() => {
    if (selectedIndex >= 0 && virtuosoRef.current) {
      virtuosoRef.current.scrollIntoView({
        index: selectedIndex,
        behavior: 'auto',
      });
    }
  }, [selectedIndex]);

  const getEmailId = useCallback(
    (index: number) => emails[index]?.id,
    [emails]
  );

  useKeyboardShortcuts({
    selectedIndex,
    setSelectedIndex,
    emailCount: emails.length,
    getEmailId,
    searchInputRef,
  });

  function handleEndReached() {
    if (emails.length < total && !loading) {
      loadEmails(emails.length, true);
    }
  }

  if (initialLoading) {
    return (
      <div className="email-list">
        <div className="email-list-header">
          <span className="email-list-count">Loading...</span>
        </div>
        <div className="email-list-skeleton">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="skeleton-row">
              <div className="skeleton-line skeleton-short" />
              <div className="skeleton-line skeleton-long" />
              <div className="skeleton-line skeleton-date" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (emails.length === 0 && !loading) {
    return (
      <div className="email-list">
        <div className="email-list-empty">
          <p>No emails found</p>
        </div>
      </div>
    );
  }

  const selectedId =
    selectedIndex >= 0 && emails[selectedIndex]
      ? emails[selectedIndex].id
      : null;

  const allEmailIds = emails.map((e) => e.id);
  const allSelected = emails.length > 0 && selection.selectedCount === emails.length;

  function handleSelectAll() {
    if (allSelected) {
      selection.clearSelection();
    } else {
      selection.selectAll(allEmailIds);
    }
  }

  function handleActionComplete() {
    // Reload the list after an action
    setEmails([]);
    setTotal(0);
    setInitialLoading(true);
    loadEmails(0, false);
  }

  return (
    <div className="email-list">
      {selection.selectedCount > 0 ? (
        <ActionToolbar
          selectedIds={selection.selectedArray}
          onActionComplete={handleActionComplete}
          onClearSelection={selection.clearSelection}
        />
      ) : (
        <div className="email-list-header">
          <div className="email-list-header-left">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={handleSelectAll}
              className="email-list-select-all"
              title="Select all"
            />
            <span className="email-list-count">
              {total.toLocaleString()} email{total !== 1 ? 's' : ''}
              {query && (
                <span className="email-list-query">
                  {' '}
                  for &ldquo;{query}&rdquo;
                </span>
              )}
              {label && !query && (
                <span className="email-list-label"> in {label}</span>
              )}
            </span>
          </div>
        </div>
      )}
      <Virtuoso
        ref={virtuosoRef}
        style={{ height: 'calc(100% - 40px)' }}
        totalCount={emails.length}
        endReached={handleEndReached}
        overscan={200}
        itemContent={(index) => {
          const email = emails[index];
          if (!email) return null;
          return (
            <EmailRow
              email={email}
              isSelected={selectedId === email.id}
              isChecked={selection.isSelected(email.id)}
              onCheckToggle={(shiftKey) => selection.toggle(email.id, index, shiftKey, allEmailIds)}
            />
          );
        }}
        components={{
          Footer: () =>
            loading ? (
              <div className="email-list-loading">Loading more...</div>
            ) : null,
        }}
      />
    </div>
  );
}
