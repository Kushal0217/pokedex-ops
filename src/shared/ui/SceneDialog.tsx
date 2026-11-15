import * as Dialog from '@radix-ui/react-dialog';
import { useLayoutEffect, useRef, type ReactNode } from 'react';
import './dialog.css';

/**
 * Open dialogs, bottom to top. Dialogs stack (a place, then its menu, then the
 * facts view) and Escape must close exactly the top one. The dialog library
 * registers its own layers a moment after opening, so a very quick Escape
 * could reach the dialog underneath; this stack is updated before paint and is
 * the single authority for Escape instead.
 */
const openDialogs: { close: () => void }[] = [];

if (typeof document !== 'undefined') {
  // Capture on window so this runs before the library's own document listener.
  window.addEventListener(
    'keydown',
    (event) => {
      if (event.key !== 'Escape' || event.repeat || openDialogs.length === 0) return;
      openDialogs[openDialogs.length - 1]!.close();
    },
    true,
  );
}

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
  const closeRef = useRef(() => onOpenChange(false));
  closeRef.current = () => onOpenChange(false);
  useLayoutEffect(() => {
    if (!open) return;
    const entry = { close: () => closeRef.current() };
    openDialogs.push(entry);
    return () => {
      openDialogs.splice(openDialogs.indexOf(entry), 1);
    };
  }, [open]);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content
          className={`dialog dialog--${tone} dialog--${size}`}
          // Escape is handled by the stack above.
          onEscapeKeyDown={(event) => event.preventDefault()}
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
