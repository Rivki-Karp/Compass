/**
 * The catalog picker for today's car (item 5): the server builds the options (manufacturer,
 * then model, then year, from the catalog), the employee picks, and the pick goes back as one
 * call. Pure, tested on its own. The employee never types a car and the agent never lists one
 * from its own knowledge: this is the list.
 */

import type { CarPicker, PickerManufacturer, PickerModel } from "../api/types";

export interface PickerPath {
  maker: string | null;
  model: string | null;
}

export const START: PickerPath = { maker: null, model: null };

export type Step = "maker" | "model" | "year";

export function step(path: PickerPath): Step {
  if (path.maker === null) return "maker";
  return path.model === null ? "model" : "year";
}

export function makerOf(picker: CarPicker, path: PickerPath): PickerManufacturer | null {
  return picker.manufacturers.find((m) => m.id === path.maker) ?? null;
}

export function modelOf(picker: CarPicker, path: PickerPath): PickerModel | null {
  return makerOf(picker, path)?.models.find((m) => m.id === path.model) ?? null;
}

/** One step back (the manufacturer list is the first step). */
export function back(path: PickerPath): PickerPath {
  if (path.model !== null) return { ...path, model: null };
  return START;
}

/** What a choice sends to POST /current-car. */
export type PickBody =
  | { choice: "car"; car_id: string }
  | { choice: "check_year"; car_id: string }
  | { choice: "not_in_list" }
  | { choice: "no_car" };
