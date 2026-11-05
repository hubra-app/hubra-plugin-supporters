import { registerPlugin } from '@hubra/plugin-sdk'
import { IconHeartHandshake } from '@tabler/icons-react'
import { GoalScreen } from './GoalScreen'
import { SupportersScreen } from './SupportersScreen'
import translations from './translations.json'

registerPlugin({
  id: 'supporters',
  routes: [
    { path: 'supporters', module: 'supporters', component: SupportersScreen },
    { path: 'supporters/sponsors', module: 'supporters', perm: 'supporters.sponsors.read', component: SupportersScreen },
    { path: 'supporters/goals/:id', module: 'supporters', component: GoalScreen },
  ],
  // The nav entry in hubra_supporters/__init__.py names this icon.
  icons: { 'heart-handshake': IconHeartHandshake },
  translations,
})
