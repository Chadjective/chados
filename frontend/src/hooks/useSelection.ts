import { useState, useCallback, useRef } from 'react';

export function useSelection() {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const lastClickedIndex = useRef<number | null>(null);

  const toggle = useCallback((id: number, index: number, shiftKey: boolean, allIds: number[]) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);

      if (shiftKey && lastClickedIndex.current !== null) {
        // Range selection
        const start = Math.min(lastClickedIndex.current, index);
        const end = Math.max(lastClickedIndex.current, index);
        for (let i = start; i <= end; i++) {
          if (allIds[i] !== undefined) {
            next.add(allIds[i]);
          }
        }
      } else {
        if (next.has(id)) {
          next.delete(id);
        } else {
          next.add(id);
        }
      }

      lastClickedIndex.current = index;
      return next;
    });
  }, []);

  const selectAll = useCallback((ids: number[]) => {
    setSelectedIds(new Set(ids));
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
    lastClickedIndex.current = null;
  }, []);

  const isSelected = useCallback((id: number) => selectedIds.has(id), [selectedIds]);

  return {
    selectedIds,
    selectedCount: selectedIds.size,
    toggle,
    selectAll,
    clearSelection,
    isSelected,
    selectedArray: Array.from(selectedIds),
  };
}
