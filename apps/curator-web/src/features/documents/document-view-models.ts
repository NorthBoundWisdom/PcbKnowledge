export interface DocumentListItemView {
  readonly documentId: string;
  readonly documentNumber?: string;
  readonly projectName: string;
  readonly revisionCreatedAt: string;
  readonly revisionId: string;
  readonly revisionLabel: string;
  readonly state: string;
  readonly title: string;
}

export interface DocumentRevisionView {
  readonly byteSize: number;
  readonly createdAt: string;
  readonly documentId: string;
  readonly documentNumber?: string;
  readonly id: string;
  readonly mediaType: string;
  readonly originalFilename: string;
  readonly projectName: string;
  readonly revisionLabel: string;
  readonly sha256: string;
  readonly sourceOrganizationName: string;
  readonly state: string;
  readonly title: string;
}

export type DownloadActivity =
  | { readonly status: "idle" }
  | { readonly status: "authorizing" }
  | { readonly status: "failed" };
