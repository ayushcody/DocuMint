"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

interface SchemaField {
  id: string;
  name: string;
  type: "string" | "number" | "date";
  required: boolean;
}

export function SchemaBuilder() {
  const [fields, setFields] = useState<SchemaField[]>([
    { id: "invoice_number", name: "invoice_number", type: "string", required: true },
    { id: "total", name: "total", type: "number", required: true }
  ]);

  function addField() {
    const nextIndex = fields.length + 1;
    setFields([
      ...fields,
      { id: `field_${nextIndex}`, name: `field_${nextIndex}`, type: "string", required: false }
    ]);
  }

  function removeField(id: string) {
    setFields(fields.filter((field) => field.id !== id));
  }

  return (
    <section className="bg-panel p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-black">Schema</h2>
        <Button aria-label="Add schema field" icon={<Plus size={16} />} onClick={addField} variant="secondary" />
      </div>
      <div className="grid gap-2">
        {fields.map((field) => (
          <div key={field.id} className="grid grid-cols-[1fr_92px_36px] gap-2">
            <input
              className="h-9 min-w-0 rounded-md border border-line bg-[#f8fbfc] px-2 text-sm font-semibold outline-none transition focus:border-teal focus:bg-white focus:ring-2 focus:ring-teal/20"
              onChange={(event) =>
                setFields(
                  fields.map((item) =>
                    item.id === field.id ? { ...item, name: event.target.value } : item
                  )
                )
              }
              value={field.name}
            />
            <select
              className="h-9 rounded-md border border-line bg-[#f8fbfc] px-2 text-sm font-semibold outline-none transition focus:border-teal focus:bg-white focus:ring-2 focus:ring-teal/20"
              onChange={(event) =>
                setFields(
                  fields.map((item) =>
                    item.id === field.id
                      ? { ...item, type: event.target.value as SchemaField["type"] }
                      : item
                  )
                )
              }
              value={field.type}
            >
              <option value="string">string</option>
              <option value="number">number</option>
              <option value="date">date</option>
            </select>
            <Button
              className="px-0"
              aria-label={`Remove ${field.name}`}
              icon={<Trash2 size={15} />}
              onClick={() => removeField(field.id)}
              variant="ghost"
            />
          </div>
        ))}
      </div>
    </section>
  );
}
