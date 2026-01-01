import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AnalysisService, YearAnalysisResponse } from '../../services/analysis.service';

@Component({
  selector: 'app-timeline',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './timeline.component.html',
  styleUrl: './timeline.component.css'
})
export class TimelineComponent implements OnInit {
  loading = true;
  error: string | null = null;
  yearsData: Map<number, any[]> = new Map(); // Map van jaar -> top 10 personen
  currentYear = 1576;
  startYear = 1576;
  endYear = 1666;
  loadedYears: number[] = [];
  consecutiveErrors = 0;
  maxConsecutiveErrors = 5; // Stop na 5 opeenvolgende fouten
  hoveredPersonId: string | null = null;
  hoveredYear: number | null = null;
  pinnedPersonId: string | null = null;
  pinnedYear: number | null = null;
  wikipediaMapping: { [key: string]: string } = {};
  personColors: Map<string, string> = new Map(); // Map van person_id -> kleur
  colorPalette: string[] = [
    '#FFB3BA', '#FFDFBA', '#FFFFBA', '#BAFFC9', '#BAE1FF',
    '#FFB6C1', '#FFDAB9', '#FFF8DC', '#E0FFE0', '#B0E0E6',
    '#F0C1C1', '#FFE4C4', '#FFFACD', '#D0F0C0', '#ADD8E6',
    '#FFB4A8', '#FFE0B2', '#FFF9C4', '#C8E6C9', '#B3E5FC',
    '#F4A5A5', '#FFCCB3', '#FFF5C2', '#B5EAD7', '#C5CAE9',
    '#FFC9DE', '#FFD4E5', '#E1BEE7', '#D1C4E9', '#C5CAE9',
    '#BBDEFB', '#B3E5FC', '#B2EBF2', '#B2DFDB', '#C8E6C9',
    '#DCEDC8', '#F0F4C3', '#FFF9C4', '#FFECB3', '#FFE0B2'
  ];
  nextColorIndex = 0;
  conflicts: { [key: string]: { name: string, wiki: string, startYear: number, endYear: number } } = {
    'eighty_years_war_1572_1576': { name: 'Eighty Years\' War (1572-1576)', wiki: 'https://en.wikipedia.org/wiki/Eighty_Years%27_War,_1572%E2%80%931576', startYear: 1572, endYear: 1576 },
    'eighty_years_war_1576_1579': { name: 'Eighty Years\' War (1576-1578)', wiki: 'https://en.wikipedia.org/wiki/Eighty_Years%27_War,_1576%E2%80%931579', startYear: 1576, endYear: 1578 },
    'eighty_years_war_1579_1588': { name: 'Eighty Years\' War (1579-1587)', wiki: 'https://en.wikipedia.org/wiki/Eighty_Years%27_War,_1579%E2%80%931588', startYear: 1579, endYear: 1587 },
    'ten_years_eighty_years_war': { name: 'Ten Years (Eighty Years\' War)', wiki: 'https://en.wikipedia.org/wiki/Ten_Years_(Eighty_Years%27_War)', startYear: 1588, endYear: 1598 },
    'eighty_years_war_1599_1609': { name: 'Eighty Years\' War (1599-1608)', wiki: 'https://en.wikipedia.org/wiki/Eighty_Years%27_War,_1599%E2%80%931609', startYear: 1599, endYear: 1608 },
    'twelve_years_truce': { name: 'Twelve Years\' Truce (1609-1620)', wiki: 'https://en.wikipedia.org/wiki/Twelve_Years%27_Truce', startYear: 1609, endYear: 1620 },
    'eighty_years_war_1621_1648': { name: 'Eighty Years\' War (1621-1648)', wiki: 'https://en.wikipedia.org/wiki/Eighty_Years%27_War,_1621%E2%80%931648', startYear: 1621, endYear: 1648 },
    'nine_years_war': { name: 'Nine Years\' War', wiki: 'https://en.wikipedia.org/wiki/Nine_Years%27_War', startYear: 1688, endYear: 1697 },
    'war_spanish_succession': { name: 'War of Spanish Succession', wiki: 'https://en.wikipedia.org/wiki/War_of_the_Spanish_Succession', startYear: 1701, endYear: 1714 },
    'war_austrian_succession': { name: 'War of Austrian Succession', wiki: 'https://en.wikipedia.org/wiki/War_of_the_Austrian_Succession', startYear: 1740, endYear: 1748 },
    'seven_years_war': { name: 'Seven Years\' War', wiki: 'https://en.wikipedia.org/wiki/Seven_Years%27_War', startYear: 1756, endYear: 1763 },
    'fourth_anglo_dutch_war': { name: 'Fourth Anglo-Dutch War', wiki: 'https://en.wikipedia.org/wiki/Fourth_Anglo-Dutch_War', startYear: 1780, endYear: 1784 },
    'war_first_coalition': { name: 'War of the First Coalition', wiki: 'https://en.wikipedia.org/wiki/War_of_the_First_Coalition', startYear: 1792, endYear: 1797 }
  };

  constructor(private analysisService: AnalysisService) {}

  ngOnInit(): void {
    // Load Wikipedia mapping
    this.analysisService.getWikipediaMapping().subscribe({
      next: (mapping) => {
        this.wikipediaMapping = mapping;
        console.log('Wikipedia mapping loaded:', Object.keys(mapping).length, 'entries');
      },
      error: (err) => {
        console.warn('Failed to load Wikipedia mapping:', err);
      }
    });
    
    this.loadYearData(this.startYear);
  }

  loadYearData(year: number): void {
    if (year > this.endYear || this.consecutiveErrors >= this.maxConsecutiveErrors) {
      this.loading = false;
      if (this.consecutiveErrors >= this.maxConsecutiveErrors) {
        console.log(`Stopped loading after ${this.maxConsecutiveErrors} consecutive errors`);
      } else {
        console.log('All years loaded');
      }
      return;
    }

    this.currentYear = year;
    
    this.analysisService.getYearAnalysis(year).subscribe({
      next: (data) => {
        // Reset error counter bij succesvolle load
        this.consecutiveErrors = 0;
        
        // Sla top 10 personen op voor dit jaar
        const topPersons = data.persons.slice(0, 10);
        this.yearsData.set(year, topPersons);
        this.loadedYears.push(year);
        
        console.log(`Loaded data for year ${year}: ${topPersons.length} persons`);
        
        // Laad volgend jaar
        setTimeout(() => {
          this.loadYearData(year + 1);
        }, 100);
      },
      error: (err) => {
        this.consecutiveErrors++;
        console.warn(`Failed to load year ${year} (${this.consecutiveErrors}/${this.maxConsecutiveErrors} consecutive errors)`);
        
        // Bij fout, probeer volgend jaar (tenzij te veel errors)
        if (this.consecutiveErrors < this.maxConsecutiveErrors) {
          setTimeout(() => {
            this.loadYearData(year + 1);
          }, 100);
        } else {
          this.loading = false;
          this.error = `Stopped loading: ${this.maxConsecutiveErrors} consecutive years not available. ${this.loadedYears.length} years loaded successfully.`;
        }
      }
    });
  }

  getTopPersonsForYear(year: number): any[] {
    const persons = this.yearsData.get(year) || [];
    // Create a copy and sort by eigenvector_centrality descending (highest first)
    const sorted = [...persons].sort((a, b) => {
      const aVal = a.eigenvector_centrality || 0;
      const bVal = b.eigenvector_centrality || 0;
      return bVal - aVal;
    });
    return sorted;
  }

  getPersonColor(personId: string): string {
    if (!this.personColors.has(personId)) {
      // Wijs nieuwe kleur toe aan deze persoon
      const color = this.colorPalette[this.nextColorIndex % this.colorPalette.length];
      this.personColors.set(personId, color);
      this.nextColorIndex++;
    }
    return this.personColors.get(personId)!;
  }

  getCircleSize(centrality: number | undefined): number {
    if (centrality === undefined || centrality === null) return 20;
    // Schaal van 15px (min) tot 45px (max) gebaseerd op centrality (0-1)
    const minSize = 15;
    const maxSize = 45;
    return minSize + (centrality * (maxSize - minSize));
  }

  onPersonHover(personId: string, year: number): void {
    this.hoveredPersonId = personId;
    this.hoveredYear = year;
  }

  onPersonLeave(): void {
    this.hoveredPersonId = null;
    this.hoveredYear = null;
  }

  onPersonClick(personId: string, year: number): void {
    this.pinnedPersonId = personId;
    this.pinnedYear = year;
  }

  getDisplayedPersonId(): string | null {
    // Als er nog niet geklikt is, toon de gehovered persoon
    if (this.pinnedPersonId === null) {
      return this.hoveredPersonId;
    }
    // Als er wel geklikt is, toon alleen de pinned persoon
    return this.pinnedPersonId;
  }

  isPersonHovered(personId: string): boolean {
    // Highlight alleen bij hover, niet bij pin
    return this.hoveredPersonId === personId;
  }

  isPersonPinned(personId: string): boolean {
    return this.pinnedPersonId === personId;
  }

  getHoveredPersonCentrality(): string {
    const personId = this.getDisplayedPersonId();
    if (!personId) return '0.00';
    
    // Bepaal welk jaar we moeten gebruiken
    const year = this.pinnedYear !== null ? this.pinnedYear : this.hoveredYear;
    if (year === null) return '0.00';
    
    // Zoek de persoon in het specifieke jaar
    const persons = this.yearsData.get(year);
    if (persons) {
      const person = persons.find(p => p.person_id === personId);
      if (person && person.eigenvector_centrality !== undefined) {
        return person.eigenvector_centrality.toFixed(2);
      }
    }
    return '0.00';
  }

  getHoveredPersonNames(): string[] {
    const personId = this.getDisplayedPersonId();
    if (!personId) return [];
    
    // Bepaal welk jaar we moeten gebruiken
    const year = this.pinnedYear !== null ? this.pinnedYear : this.hoveredYear;
    if (year === null) return [];
    
    // Zoek de persoon in het specifieke jaar
    const persons = this.yearsData.get(year);
    if (persons) {
      const person = persons.find(p => p.person_id === personId);
      if (person && person.names) {
        return person.names;
      }
    }
    return [];
  }

  getPersonSearchUrl(): string {
    const personId = this.getDisplayedPersonId();
    if (!personId) return '';
    
    // Check if person has Wikipedia link
    if (this.wikipediaMapping[personId]) {
      return this.wikipediaMapping[personId];
    }
    
    // Fallback to DuckDuckGo
    const names = this.getHoveredPersonNames();
    if (names.length === 0) return '';
    const encodedName = encodeURIComponent(names[0]);
    return `https://duckduckgo.com/?q=${encodedName}`;
  }

  getPersonDisplayName(): string {
    const personId = this.getDisplayedPersonId();
    if (!personId) return '';
    
    // Check if person has Wikipedia link
    if (this.wikipediaMapping[personId]) {
      const wikiUrl = this.wikipediaMapping[personId];
      // Extract suffix after last /
      const parts = wikiUrl.split('/');
      const suffix = parts[parts.length - 1];
      // Replace underscores with spaces and decode URI
      return decodeURIComponent(suffix.replace(/_/g, ' '));
    }
    
    // Fallback to first name
    const names = this.getHoveredPersonNames();
    return names.length > 0 ? names[0] : '';
  }

  hasWikipediaLink(): boolean {
    const personId = this.getDisplayedPersonId();
    return personId ? !!this.wikipediaMapping[personId] : false;
  }

  getConnectionLines(): any[] {
    const lines: any[] = [];
    
    // Detecteer mobiel scherm (check of window beschikbaar is voor SSR)
    const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
    
    for (let i = 0; i < this.loadedYears.length - 1; i++) {
      const currentYear = this.loadedYears[i];
      const nextYear = this.loadedYears[i + 1];
      
      const currentPersons = this.getTopPersonsForYear(currentYear);
      const nextPersons = this.getTopPersonsForYear(nextYear);
      
      // Bereken startpositie voor circles:
      // Desktop: padding-top (10px) + year-label height (~15px) + margin-bottom (45px) = 70px
      // Mobile: padding-top (10px) + year-label height (~15px) + margin-bottom (10px) = 35px
      const circlesStartY = isMobile ? 48 : 88;
      const columnWidth = isMobile ? 60 : 80;
      
      currentPersons.forEach((person, personIndex) => {
        const nextYearIndex = nextPersons.findIndex(p => p.person_id === person.person_id);
        
        if (nextYearIndex !== -1) {
          // Bereken Y positie voor volgend jaar
          let nextY = circlesStartY;
          const nextPersonsSubset = nextPersons.slice(0, nextYearIndex);
          
          // Tel alle voorgaande cirkels op voor nextY
          for (let j = 0; j < nextYearIndex; j++) {
            const circleSizeNext = this.getCircleSize(nextPersonsSubset[j].eigenvector_centrality);
            const circleMargin = isMobile ? 5 : 7;
            nextY += circleMargin + circleSizeNext + circleMargin;
          }
          
          // Add center offset voor de target cirkel
          const nextCircleSize = this.getCircleSize(nextPersons[nextYearIndex].eigenvector_centrality);
          const circleMargin = isMobile ? 5 : 7;
          nextY += circleMargin + (nextCircleSize / 2);
          
          // Bereken currentY inclusief center offset
          const currentCircleSize = this.getCircleSize(person.eigenvector_centrality);
          const currentPersonsSubset = currentPersons.slice(0, personIndex);
          let yForThisPerson = circlesStartY;
          
          for (let j = 0; j < personIndex; j++) {
            const circleSizeCurrent = this.getCircleSize(currentPersonsSubset[j].eigenvector_centrality);
            const circleMargin = isMobile ? 5 : 7;
            yForThisPerson += circleMargin + circleSizeCurrent + circleMargin;
          }
          yForThisPerson += circleMargin + (currentCircleSize / 2);
          
          lines.push({
            fromYear: i,
            fromIndex: personIndex,
            toYear: i + 1,
            toIndex: nextYearIndex,
            color: this.getPersonColor(person.person_id),
            personId: person.person_id,
            y1: yForThisPerson,
            y2: nextY,
            x1: (i * columnWidth) + (columnWidth / 2),
            x2: ((i + 1) * columnWidth) + (columnWidth / 2)
          });
        }
      });
    }
    
    return lines;
  }

  getCurvePath(x1: number, y1: number, x2: number, y2: number): string {
    // Bereken control points voor een mooie S-curve
    const midX = (x1 + x2) / 2;
    const yDiff = Math.abs(y2 - y1);
    const curvature = Math.min(yDiff * 0.3, 30); // Max 30px curvature
    
    // Control points voor smooth S-curve
    const cp1x = x1 + (midX - x1) * 0.5;
    const cp1y = y1;
    const cp2x = x2 - (x2 - midX) * 0.5;
    const cp2y = y2;
    
    return `M ${x1} ${y1} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x2} ${y2}`;
  }

  getConflictForYear(year: number): { name: string, wiki: string } | null {
    for (const conflict of Object.values(this.conflicts)) {
      if (year >= conflict.startYear && year <= conflict.endYear) {
        return { name: conflict.name, wiki: conflict.wiki };
      }
    }
    return null;
  }

  getConflictBlocks(): { startIndex: number, width: number, name: string, wiki: string, startYear: number, endYear: number }[] {
    const blocks: { startIndex: number, width: number, name: string, wiki: string, startYear: number, endYear: number }[] = [];
    
    if (this.loadedYears.length === 0) return blocks;
    
    const firstLoadedYear = this.loadedYears[0];
    const lastLoadedYear = this.loadedYears[this.loadedYears.length - 1];
    
    for (const conflict of Object.values(this.conflicts)) {
      // Check of conflict overlapt met geladen jaren
      if (conflict.endYear >= firstLoadedYear && conflict.startYear <= lastLoadedYear) {
        // Bereken welk jaar als eerste moet worden getoond
        const displayStartYear = Math.max(conflict.startYear, firstLoadedYear);
        const displayEndYear = Math.min(conflict.endYear, lastLoadedYear);
        
        const startIndex = this.loadedYears.findIndex(y => y === displayStartYear);
        const endIndex = this.loadedYears.findIndex(y => y === displayEndYear);
        
        if (startIndex !== -1) {
          const endIdx = endIndex !== -1 ? endIndex : this.loadedYears.length - 1;
          const yearSpan = endIdx - startIndex + 1;
          
          blocks.push({
            startIndex: startIndex,
            width: yearSpan * 80 - 20, // 80px per jaar, minus 20px for margins
            name: conflict.name,
            wiki: conflict.wiki,
            startYear: conflict.startYear,
            endYear: conflict.endYear
          });
        }
      }
    }
    
    return blocks;
  }

  hasConflict(year: number): boolean {
    // Check if this year falls within any conflict period
    for (const conflict of Object.values(this.conflicts)) {
      if (year >= conflict.startYear && year <= conflict.endYear) {
        return true;
      }
    }
    return false;
  }

  getConflictWikiUrl(year: number): string | null {
    // Get Wikipedia URL for conflict in this year
    for (const conflict of Object.values(this.conflicts)) {
      if (year >= conflict.startYear && year <= conflict.endYear) {
        return conflict.wiki;
      }
    }
    return null;
  }

  getPersonIndexInYear(year: number, personId: string): number {
    const persons = this.getTopPersonsForYear(year);
    return persons.findIndex(p => p.person_id === personId);
  }
}
