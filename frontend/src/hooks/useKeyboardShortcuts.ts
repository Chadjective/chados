import { useEffect, useCallback, type RefObject } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

interface UseKeyboardShortcutsOptions {
  selectedIndex: number;
  setSelectedIndex: (fn: (prev: number) => number) => void;
  emailCount: number;
  getEmailId: (index: number) => number | undefined;
  searchInputRef: RefObject<HTMLInputElement | null>;
}

export function useKeyboardShortcuts({
  selectedIndex,
  setSelectedIndex,
  emailCount,
  getEmailId,
  searchInputRef,
}: UseKeyboardShortcutsOptions) {
  const navigate = useNavigate();
  const location = useLocation();

  const isListView =
    location.pathname === '/' ||
    location.pathname.startsWith('/label/') ||
    location.pathname.startsWith('/search');

  const isDetailView =
    location.pathname.startsWith('/email/') ||
    location.pathname.startsWith('/thread/');

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === 'INPUT' || target.tagName === 'TEXTAREA';

      // "/" focuses search bar from anywhere
      if (e.key === '/' && !isInput) {
        e.preventDefault();
        searchInputRef.current?.focus();
        return;
      }

      // Escape: go back to list from detail view, or blur search
      if (e.key === 'Escape') {
        if (isInput) {
          (target as HTMLInputElement).blur();
          return;
        }
        if (isDetailView) {
          e.preventDefault();
          navigate(-1);
          return;
        }
      }

      // Don't handle j/k/Enter when typing in an input
      if (isInput) return;

      if (isListView) {
        if (e.key === 'j' || e.key === 'ArrowDown') {
          e.preventDefault();
          setSelectedIndex((prev) => Math.min(prev + 1, emailCount - 1));
        } else if (e.key === 'k' || e.key === 'ArrowUp') {
          e.preventDefault();
          setSelectedIndex((prev) => Math.max(prev - 1, 0));
        } else if (e.key === 'Enter' && selectedIndex >= 0) {
          e.preventDefault();
          const emailId = getEmailId(selectedIndex);
          if (emailId !== undefined) {
            navigate(`/email/${emailId}`);
          }
        }
      }
    },
    [
      isListView,
      isDetailView,
      selectedIndex,
      emailCount,
      getEmailId,
      navigate,
      searchInputRef,
      setSelectedIndex,
    ]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
