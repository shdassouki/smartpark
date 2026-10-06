// Static frontend configuration for the currently seeded prototype options.
// These values match the DynamoDB seed data (data/seed_dynamo.py).
// If the seed data changes, update these lists to match.

export interface SelectOption {
  value: string
  label: string
}

export const BUILDING_OPTIONS: SelectOption[] = [
  { value: 'bldg_enterprise', label: 'Enterprise Hall' },
  { value: 'bldg_johnson', label: 'Johnson Center' },
  { value: 'bldg_exploratory', label: 'Exploratory Hall' },
]

export const PERMIT_OPTIONS: SelectOption[] = [
  { value: 'GENERAL', label: 'General' },
  { value: 'FACULTY_STAFF', label: 'Faculty/Staff' },
]
