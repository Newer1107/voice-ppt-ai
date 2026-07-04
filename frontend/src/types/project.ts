export interface Project {
  id: string;
  title: string;
  description?: string;
  status: string;
  lecture_count: number;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
