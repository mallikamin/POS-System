import { useRef, useState } from "react";
import { Image as ImageIcon, Loader2, Upload, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { uploadImage } from "@/services/mediaApi";

interface ImageFieldProps {
  value: string | null;
  onChange: (url: string | null) => void;
  label?: string;
  /** Used to make the file input's id unique when two forms share a page. */
  idPrefix?: string;
}

/**
 * Photo picker for the menu item and ingredient forms.
 *
 * Choosing a file uploads it immediately and hands the resulting URL to the
 * form, which stores it with the rest of the record on save. Removing clears
 * the URL on the record only; the stored bytes stay addressable by anything
 * else that still points at them.
 */
export function ImageField({
  value,
  onChange,
  label = "Photo",
  idPrefix = "image",
}: ImageFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const { toast } = useToast();
  const inputId = `${idPrefix}-file`;

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    try {
      const media = await uploadImage(file);
      onChange(media.url);
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      toast({
        variant: "destructive",
        title:
          status === 413
            ? "That photo is too large (5 MB limit)"
            : typeof detail === "string"
              ? detail
              : "Could not upload the photo",
      });
    } finally {
      setUploading(false);
      // Allow re-selecting the same file after a failure or a Remove.
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={inputId}>{label}</Label>
      <div className="flex items-start gap-4">
        <div className="aspect-[4/3] w-40 shrink-0 overflow-hidden rounded-lg border border-secondary-200 bg-secondary-100">
          {value ? (
            <img
              src={value}
              alt=""
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-secondary-400">
              <ImageIcon className="h-8 w-8" aria-hidden="true" />
            </div>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept="image/*"
            className="sr-only"
            onChange={(e) => handleFile(e.target.files?.[0])}
            disabled={uploading}
          />
          <Button
            type="button"
            variant="outline"
            className="min-h-touch"
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            {uploading ? "Uploading…" : value ? "Replace photo" : "Upload photo"}
          </Button>
          {value && !uploading && (
            <Button
              type="button"
              variant="ghost"
              className="min-h-touch text-danger-600 hover:text-danger-700"
              onClick={() => onChange(null)}
            >
              <X className="h-4 w-4" />
              Remove
            </Button>
          )}
          <p className="text-xs text-secondary-500">
            JPEG, PNG or WebP. Resized automatically.
          </p>
        </div>
      </div>
    </div>
  );
}
