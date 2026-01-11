import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, tap } from 'rxjs/operators';

export interface PersonAnalysis {
  person_id: string;
  connection_count: number;
  year: number;
  analyzed_at: string;
  names: string[];
  documents: string[];
  eigenvector_centrality?: number;
}

export interface YearAnalysisResponse {
  status: string;
  count: number;
  total: number;
  skip: number;
  limit: number;
  year: number;
  persons: PersonAnalysis[];
}

@Injectable({
  providedIn: 'root'
})
export class AnalysisService {
  private yearCache: Map<number, YearAnalysisResponse> = new Map();
  private perEntitiesCache: any[] | null = null;

  constructor(private http: HttpClient) { }

  /**
   * Get analysis data for a specific year from the public/analysis folder
   * @param year The year to retrieve analysis data for (e.g., 1600)
   * @returns Observable with the year's analysis data (sorted by centrality)
   */
  getYearAnalysis(year: number): Observable<YearAnalysisResponse> {
    // Check cache first
    if (this.yearCache.has(year)) {
      return of(this.yearCache.get(year)!);
    }

    return this.http.get<YearAnalysisResponse>(`/analysis/${year}.json`).pipe(
      map(response => {
        return response;
      }),
      tap(response => {
        // Store in cache
        this.yearCache.set(year, response);
      })
    );
  }

  getPersonEntities(): Observable<any[]> {
    // Check cache first
    if (this.perEntitiesCache) {
      return of(this.perEntitiesCache);
    }

    return this.http.get<any[]>('/PER-entities.json').pipe(
      tap(entities => {
        // Store in cache
        this.perEntitiesCache = entities;
      })
    );
  }
}
