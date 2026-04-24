import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { Race, Driver, Stint } from '../lib/types'

export function useRaces() {
  return useQuery<Race[]>({
    queryKey: ['races'],
    queryFn: () => apiFetch<Race[]>('/races'),
    staleTime: Infinity,  // race data for completed seasons never changes
  })
}

export function useDrivers(raceId: string | null) {
  return useQuery<Driver[]>({
    queryKey: ['drivers', raceId],
    queryFn: () => apiFetch<Driver[]>(`/races/${raceId!}/drivers`),
    enabled: !!raceId,
    staleTime: Infinity,
  })
}

export function useStints(raceId: string | null, driverCode: string | null) {
  return useQuery<Stint[]>({
    queryKey: ['stints', raceId, driverCode],
    queryFn: () => apiFetch<Stint[]>(`/stints/${raceId!}/${driverCode!}`),
    enabled: !!raceId && !!driverCode,
    staleTime: Infinity,
  })
}
