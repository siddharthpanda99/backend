type GenericObject = Record<string, any>;

export interface SortFilterOptions {
    sortField?: string;
    sortOrder?: 'asc' | 'desc';
    filters?: Record<string, any>;
}

export function sortAndFilterList<T extends GenericObject>(list: T[], options?: SortFilterOptions): T[] {
    let filteredList = [...list];

    // Apply filters
    if (options?.filters) {
        filteredList = filteredList.filter((item) => {
            return Object.entries(options.filters).every(([key, value]) => {
                return item[key] === value;
            });
        });
    }

    // Apply sorting
    if (options?.sortField !== undefined) {
        filteredList.sort((a, b) => {
            const aValue = a[options.sortField as keyof T];
            const bValue = b[options.sortField as keyof T];

            if (options.sortOrder === 'desc') {
                return bValue - aValue;
            } else {
                return aValue - bValue;
            }
        });
    }

    return filteredList;
}
