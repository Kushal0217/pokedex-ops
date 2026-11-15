import * as Dialog from '@radix-ui/react-dialog';
import type { ReactNode } from 'react';
import './dialog.css';

/**
 * Escape presses already used to close a dialog. Dialogs stack (interior, then
 * menu, then facts); when the top one unmounts instantly (reduced motion) the
 * next one would otherwise see the same key press and close as well.
 */
const usedEscapes = new WeakSet<Event>();

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** One-line description read out with the title. */
  description: string;
  /** Label for the close control, e.g. "Back to town". */
  closeLabel: string;
  /** Visual treatment of the header bar. */
  tone?: 'scene' | 'menu' | 'plain';
  size?: 'wide' | 'narrow';
  /** Decorative mark shown before the title. */
  mark?: ReactNode;
  /** Extra header controls (e.g. the persistent "Just the facts" action). */
  actions?: ReactNode;
  /** Runs when the dialog has closed; return focus to the launching control here. */
  onReturnFocus?: () => void;
  children: ReactNode;
}

/**
 * The shared scene/panel behaviour for every place and view:
 * modal focus trap, Escape to close, background made inert and scroll-locked
 * (the map keeps its scroll position), visible close control, and focus
 * returned to whatever launched it.
 */
export function SceneDialog({
  open, onOpenChange, title, description, closeLabel, tone = 'scene', size = 'wide', mark, actions, onReturnFocus, children,
}: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content
          className={`dialog dialog--${tone} dialog--${size}`}
          onEscapeKeyDown={(event) => {
            if (usedEscapes.has(event)) event.preventDefault();
            else usedEscapes.add(event);
          }}
          onCloseAutoFocus={(event) => {
            if (onReturnFocus) {
              event.preventDefault();
              onReturnFocus();
            }
          }}
        >
          <header className="dialog__head">
            {mark}
            <Dialog.Title className="dialog__title">{title}</Dialog.Title>
            {actions}
            <Dialog.Close className="dialog__close">
              <span aria-hidden="true">×</span>
              <span className="dialog__close-label">{closeLabel}</span>
            </Dialog.Close>
          </header>
          <Dialog.Description className="visually-hidden">{description}</Dialog.Description>
          <div className="dialog__body">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
