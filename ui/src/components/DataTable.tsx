import { useMemo, useState, type ReactNode } from 'react';
import { EmptyState } from './Panel';

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  /** Sort value. Omit to make the column unsortable. */
  sortValue?: (row: T) => string | number | null;
  align?: 'left' | 'right';
  width?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  selectedKey,
  emptyTitle = 'No rows match the current filters',
  emptyDetail,
  maxHeight,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  selectedKey?: string | null;
  emptyTitle?: string;
  emptyDetail?: ReactNode;
  maxHeight?: number;
}) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [direction, setDirection] = useState<'asc' | 'desc'>('desc');

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const column = columns.find((c) => c.key === sortKey);
    if (!column?.sortValue) return rows;
    const factor = direction === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = column.sortValue!(a);
      const bv = column.sortValue!(b);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * factor;
      return String(av).localeCompare(String(bv)) * factor;
    });
  }, [rows, columns, sortKey, direction]);

  if (rows.length === 0) {
    return <EmptyState title={emptyTitle} detail={emptyDetail} />;
  }

  const toggleSort = (column: Column<T>) => {
    if (!column.sortValue) return;
    if (sortKey === column.key) {
      setDirection(direction === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(column.key);
      setDirection('desc');
    }
  };

  return (
    <div className="table-wrap" style={maxHeight ? { maxHeight } : undefined}>
      <table className="data">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className={column.sortValue ? 'sortable' : undefined}
                style={{
                  textAlign: column.align === 'right' ? 'right' : 'left',
                  width: column.width,
                }}
                onClick={() => toggleSort(column)}
                aria-sort={
                  sortKey === column.key
                    ? direction === 'asc'
                      ? 'ascending'
                      : 'descending'
                    : undefined
                }
              >
                {column.header}
                {sortKey === column.key ? (direction === 'asc' ? ' \u2191' : ' \u2193') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const key = rowKey(row);
            const classes = [onRowClick ? 'clickable' : '', selectedKey === key ? 'selected' : '']
              .filter(Boolean)
              .join(' ');
            return (
              <tr
                key={key}
                className={classes || undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    style={{ textAlign: column.align === 'right' ? 'right' : 'left' }}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
