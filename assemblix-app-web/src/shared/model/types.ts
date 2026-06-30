export interface PaginationResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}
