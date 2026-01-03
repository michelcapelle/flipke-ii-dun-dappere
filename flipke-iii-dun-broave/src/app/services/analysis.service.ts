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
  private wikipediaCache: { [key: string]: string } | null = null;

  constructor(private http: HttpClient) { }

  /**
   * Get analysis data for a specific year from the public/analysis folder
   * @param year The year to retrieve analysis data for (e.g., 1600)
   * @returns Observable with the year's analysis data (sorted by centrality, top 10)
   */
  getYearAnalysis(year: number): Observable<YearAnalysisResponse> {
    // Check cache first
    if (this.yearCache.has(year)) {
      return of(this.yearCache.get(year)!);
    }

    return this.http.get<YearAnalysisResponse>(`/analysis/${year}.json`).pipe(
      map(response => {
        // Sort persons by eigenvector_centrality (high to low) and take top 10
        if (response.persons && response.persons.length > 0) {
          response.persons = response.persons
            .sort((a, b) => (b.eigenvector_centrality || 0) - (a.eigenvector_centrality || 0))
            .slice(0, 10);
        }
        return response;
      }),
      tap(response => {
        // Store in cache
        this.yearCache.set(year, response);
      })
    );
  }

  getWikipediaMapping(): Observable<{ [key: string]: string }> {
    // Check cache first
    if (this.wikipediaCache) {
      return of(this.wikipediaCache);
    }

    return this.http.get<{ [key: string]: string }>('/wikipedia.json').pipe(
      tap(mapping => {
        // Store in cache
        this.wikipediaCache = mapping;
      })
    );
  }
}
