import { Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ErrorBanner, LoadingSpinner, PageHead, useT } from '@hubra/plugin-sdk'
import { QK, errorText, getOptions } from './api'
import { GoalsTab } from './GoalsTab'
import { SponsorsTab } from './SponsorsTab'

/** Supporters: the fundraising goals, for every member. */
export function SupportersScreen() {
  const { t } = useT()
  const options = useQuery({ queryKey: QK.options, queryFn: getOptions })

  if (options.isLoading) return <LoadingSpinner />
  if (options.error) return <ErrorBanner message={errorText(options.error)} onRetry={() => options.refetch()} />

  return (
    <>
      <PageHead title={t('supporters.title')} desc={t('supporters.desc')} />
      <GoalsTab options={options.data} />
    </>
  )
}

/** The sponsors, as a page tab of Finanzen (/app/finance/sponsors). */
export function SponsorsFinanceTab() {
  const options = useQuery({ queryKey: QK.options, queryFn: getOptions })

  if (options.isLoading) return <LoadingSpinner />
  if (options.error) return <ErrorBanner message={errorText(options.error)} onRetry={() => options.refetch()} />

  return <SponsorsTab options={options.data} />
}

/** The sponsors' old address, /app/supporters/sponsors, opens them in Finanzen. */
export function SponsorsMoved() {
  return <Navigate to="/app/finance/sponsors" replace />
}
