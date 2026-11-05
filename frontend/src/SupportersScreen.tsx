import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { IconBuildingStore, IconTargetArrow } from '@tabler/icons-react'
import { ErrorBanner, LoadingSpinner, PageHead, Tabs, useT } from '@hubra/plugin-sdk'
import { QK, errorText, getOptions } from './api'
import { GoalsTab } from './GoalsTab'
import { SponsorsTab } from './SponsorsTab'

/** Supporters: fundraising goals for everyone, sponsors for the board. */
export function SupportersScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const location = useLocation()
  const options = useQuery({ queryKey: QK.options, queryFn: getOptions })
  const part = location.pathname.split('/app/supporters')[1]?.replace(/^\//, '').split('/')[0] ?? ''
  const tabs = [
    { id: 'goals', label: t('supporters.tabs.goals'), icon: <IconTargetArrow size={16} />, show: true },
    { id: 'sponsors', label: t('supporters.tabs.sponsors'), icon: <IconBuildingStore size={16} />, show: !!options.data?.can.sponsorsRead },
  ].filter((tb) => tb.show)
  const active = tabs.find((tb) => tb.id === part)?.id ?? 'goals'

  if (options.isLoading) return <LoadingSpinner />
  if (options.error) return <ErrorBanner message={errorText(options.error)} onRetry={() => options.refetch()} />

  return (
    <>
      <PageHead title={t('supporters.title')} desc={t('supporters.desc')} />
      {tabs.length > 1 && (
        <Tabs tabs={tabs} activeTab={active} onTabChange={(id) => navigate(id === 'goals' ? '/app/supporters' : `/app/supporters/${id}`)} />
      )}
      {active === 'goals' && <GoalsTab options={options.data} />}
      {active === 'sponsors' && <SponsorsTab options={options.data} />}
    </>
  )
}
