export interface Word {
  text: string;
  beginTime: number;
  endTime: number;
  isFiller?: boolean;
}

export interface Segment {
  id: string;
  type: 'speech' | 'silence';
  text: string;
  beginTime: number;
  endTime: number;
  time: string;
  words?: Word[];
  hasFiller?: boolean;
  selected?: boolean;
  expanded?: boolean;
}

export interface KaipaiEditorProps {
  editId: string;
  videoUrl: string;
  onBack: () => void;
  onSave?: () => void;
}

export interface EditModalProps {
  isOpen: boolean;
  segment: Segment | null;
  onClose: () => void;
  onSave: (segmentId: string, newText: string) => void;
}

export interface SegmentItemProps {
  segment: Segment;
  isSelected: boolean;
  onToggle: (id: string) => void;
  onJump: (time: number) => void;
  onEdit: (segment: Segment) => void;
  onToggleExpand: (id: string) => void;
  onWordEdit: (segmentId: string, wordBeginTime: number, newText: string) => void;
}

export interface VideoPlayerProps {
  videoUrl: string;
  currentTime: number;
  isPlaying: boolean;
  subtitle: string;
  progressPercent: number;
  totalDuration: number;
  allAsrSegments: Segment[];
  removedIds: Set<string>;
  onTogglePlay: () => void;
  onTimeUpdate: (time: number) => void;
  onEnded: () => void;
  onSeek: (timeMs: number) => void;
  onSubtitleChange: (text: string, activeSegmentId: string | null) => void;
}
