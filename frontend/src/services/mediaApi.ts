import api from "@/lib/axios";
import { prepareImageForUpload } from "@/utils/imagePrep";

export interface MediaUpload {
  id: string;
  /** Relative path, ready to be written into an `image_url` as-is. */
  url: string;
  content_type: string;
  size_bytes: number;
  width: number;
  height: number;
}

/**
 * Upload a photograph and get back the URL to store on the record.
 *
 * The file is downscaled in the browser first (see `prepareImageForUpload`),
 * then normalised again server-side. The JSON default Content-Type is stripped
 * for FormData in the axios request interceptor, so the browser sets multipart
 * with its own boundary.
 */
export async function uploadImage(file: File): Promise<MediaUpload> {
  const blob = await prepareImageForUpload(file);
  const form = new FormData();
  const name =
    blob === file ? file.name : file.name.replace(/\.[^.]+$/, "") + ".jpg";
  form.append("file", blob, name);
  const { data } = await api.post<MediaUpload>("/media/images", form);
  return data;
}
