/**
 * Type explicite pour un fichier uploade via multer.
 *
 * On ne dépend pas du namespace global `Express.Multer.File` qui change
 * entre versions de `@types/multer`. Cette interface couvre les champs que
 * multer remplit en mode in-memory (le seul utilisé V1).
 */
export interface UploadedFile {
  fieldname: string;
  originalname: string;
  encoding: string;
  mimetype: string;
  size: number;
  buffer: Buffer;
}
