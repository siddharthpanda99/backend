type GenericObject = Record<string, any>;

export interface SortFilterOptions {
    sortFields?: string | string[];
    sortOrder?: 'asc' | 'desc';
    filters?: Record<string, string | string[]>;
}

export const sortAndFilterList = <T extends GenericObject>(list: T[], options: SortFilterOptions): T[] => {
    let filteredList = [...list];

    // Apply filters
    if (options.filters) {
        filteredList = filteredList.filter((item) => {
            return Object.entries(options.filters || {}).every(([key, value]) => {
                const itemValue = item[key];

                if (Array.isArray(value)) {
                    // If filter value is an array, check if item value is included in the array
                    return value.includes(itemValue);
                } else {
                    // If filter value is a single value, check for equality
                    return itemValue === value;
                }
            });
        });
    }

    // Apply sorting
    if (options.sortFields && options.sortFields.length > 0) {
        filteredList.sort((a, b) => {
            if (options.sortFields) {
                for (const sortField of options.sortFields) {
                    const aValue = a[sortField as keyof T];
                    const bValue = b[sortField as keyof T];

                    if (aValue !== bValue) {
                        return options.sortOrder === 'desc' ? bValue - aValue : aValue - bValue;
                    }
                }
            }

            return 0;
        });
    }

    return filteredList;
};