// Message type for chat interactions
export interface Message {
  id: number;
  text: string;
  isUser: boolean;
}