/**
 * Shrink a photo in the browser before it is uploaded.
 *
 * A phone camera produces 3-8 MB JPEGs. nginx in front of the API caps request
 * bodies at 5 MB (`client_max_body_size 5M`), so without this a manager
 * photographing a croissant on a phone would hit a 413 on roughly every other
 * attempt. Drawing through a canvas at 1600 px on the long side brings that to
 * a few hundred KB, and `imageOrientation: "from-image"` honours the EXIF
 * rotation so portrait shots do not arrive sideways.
 *
 * Best effort only. Anything the browser cannot decode (HEIC on a non-Apple
 * browser, say) is sent as-is and the server decides; it re-encodes everything
 * it accepts anyway.
 */

const MAX_SIDE = 1600;
const JPEG_QUALITY = 0.85;
// Under this size a small image is sent untouched; re-encoding it would only
// lose quality for no bandwidth win.
const PASSTHROUGH_BYTES = 1.5 * 1024 * 1024;

export async function prepareImageForUpload(file: File): Promise<Blob> {
  if (!file.type.startsWith("image/") || typeof createImageBitmap !== "function") {
    return file;
  }
  let bitmap: ImageBitmap | null = null;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const longSide = Math.max(bitmap.width, bitmap.height);
    const scale = Math.min(1, MAX_SIDE / longSide);
    if (scale === 1 && file.size <= PASSTHROUGH_BYTES) {
      return file;
    }
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    // Flatten transparency onto white, matching what the server does.
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY)
    );
    return blob ?? file;
  } catch {
    return file;
  } finally {
    bitmap?.close();
  }
}
