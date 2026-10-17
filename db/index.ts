import { drizzle } from 'drizzle-orm/netlify-db'

import * as schema from './schema'

export function getDb() {
  return drizzle({ schema })
}
