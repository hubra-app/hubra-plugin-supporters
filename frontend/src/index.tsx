import { registerPlugin } from '@hubra/plugin-sdk'
import { IconHeartHandshake } from '@tabler/icons-react'
import { GoalScreen } from './GoalScreen'
import { SponsorsFinanceTab, SponsorsMoved, SupportersScreen } from './SupportersScreen'
import translations from './translations.json'

registerPlugin({
  id: 'supporters',
  routes: [
    { path: 'supporters', module: 'supporters', component: SupportersScreen },
    { path: 'supporters/sponsors', module: 'supporters', perm: 'supporters.sponsors.read', component: SponsorsMoved },
    { path: 'supporters/goals/:id', module: 'supporters', component: GoalScreen },
  ],
  // The sponsors are money matters for the board, so they live in Finanzen
  // as a page tab of their own; the goals stay on the Supporters page.
  tabs: [
    {
      screen: 'finance',
      id: 'sponsors',
      label: 'supporters.tabs.sponsors',
      module: 'supporters',
      perm: 'supporters.sponsors.read',
      component: SponsorsFinanceTab,
    },
  ],
  // The nav entry in hubra_supporters/__init__.py names this icon.
  icons: { 'heart-handshake': IconHeartHandshake },
  translations,
})
