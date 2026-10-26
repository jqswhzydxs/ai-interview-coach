import { FileText, Upload, X } from "lucide-react";
import { useId, type ChangeEvent } from "react";

interface TextInputProps {
  id: string;
  value: string;
  onChange: (value: string) => void;
  onBlur?: (() => void) | undefined;
  disabled?: boolean | undefined;
  error?: string | undefined;
}

function SensitiveTextArea({
  id,
  label,
  helper,
  optional = false,
  value,
  onChange,
  onBlur,
  disabled,
  error,
}: TextInputProps & {
  label: string;
  helper: string;
  optional?: boolean;
}) {
  const errorId = `${id}-error`;
  const helperId = `${id}-helper`;
  return (
    <div className="field-group">
      <label htmlFor={id}>
        {label} {optional ? <span className="optional-label">（可选）</span> : null}
      </label>
      <p id={helperId} className="field-helper">{helper}</p>
      <textarea
        id={id}
        value={value}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={`${helperId}${error ? ` ${errorId}` : ""}`}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onBlur}
        rows={8}
      />
      {error ? <p id={errorId} className="field-error">{error}</p> : null}
    </div>
  );
}

export function ResumeInput(props: TextInputProps) {
  return (
    <SensitiveTextArea
      {...props}
      label="简历内容"
      helper="粘贴用于本次准备任务的简历内容。内容只保存在当前页面内存中。"
    />
  );
}

export function JobInput(props: TextInputProps) {
  return (
    <SensitiveTextArea
      {...props}
      label="职位描述（JD）"
      helper="粘贴目标岗位职责、要求和技术栈。"
    />
  );
}

export function ExperienceInput(props: TextInputProps) {
  return (
    <SensitiveTextArea
      {...props}
      optional
      label="面经内容"
      helper="可补充公开面经或个人整理；不填写也可以继续。"
    />
  );
}

export function UploadDropzone({
  file,
  accept = ".pdf,.docx,.txt",
  error,
  disabled,
  onSelect,
  onCancel,
}: {
  file: File | null;
  accept?: string | undefined;
  error?: string | undefined;
  disabled?: boolean | undefined;
  onSelect: (file: File | null) => void;
  onCancel: () => void;
}) {
  const id = useId();
  const errorId = `${id}-error`;
  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    onSelect(event.target.files?.[0] ?? null);
  };
  return (
    <div className="upload-field">
      <span id={`${id}-label`} className="field-label">上传简历文件</span>
      <p id={`${id}-help`} className="field-helper">
        支持 PDF、DOCX、TXT，最大 10 MiB；服务端执行最终校验。也可以直接粘贴文本。
      </p>
      {file ? (
        <div className="selected-file">
          <FileText aria-hidden="true" />
          <span>{file.name}</span>
          <button type="button" className="text-button" onClick={onCancel} disabled={disabled}>
            <X aria-hidden="true" size={18} /> 移除文件
          </button>
        </div>
      ) : (
        <label className="upload-button" htmlFor={id}>
          <Upload aria-hidden="true" size={20} />
          选择文件
          <input
            id={id}
            className="visually-hidden"
            type="file"
            accept={accept}
            disabled={disabled}
            aria-labelledby={`${id}-label`}
            aria-describedby={`${id}-help${error ? ` ${errorId}` : ""}`}
            aria-invalid={Boolean(error)}
            onChange={handleFile}
          />
        </label>
      )}
      {error ? <p id={errorId} className="field-error">{error}</p> : null}
    </div>
  );
}
