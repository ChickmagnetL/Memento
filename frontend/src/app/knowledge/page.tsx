import { listDocuments, type DocumentRecord } from "@/lib/api";
import { DocumentManager } from "./document-manager";

export default async function KnowledgePage() {
  let documents: DocumentRecord[] = [];
  try {
    documents = await listDocuments();
  } catch {
    documents = [];
  }

  return <DocumentManager initialDocuments={documents} />;
}
