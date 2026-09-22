const path = require('path')

module.exports = {
  version: "2.0",
  title: "Real-Time NLP Feedback Intelligence",
  description: "Real-Time Customer Feedback Sentiment Classification using Transformers & MLOps",
  icon: "icon.png",
  menu: async (kernel, info) => {
    // Check if the isolated environment exists
    let installed = info.exists("env")

    // Check currently running scripts
    let running = {
      install: info.running("install.json"),
      start: info.running("start.json"),
      reset: info.running("reset.json")
    }

    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Installing",
        href: "install.json"
      }]
    }

    if (installed) {
      if (running.start) {
        let local = info.local("start.json")
        if (local && local.url) {
          return [{
            default: true,
            icon: "fa-solid fa-rocket",
            text: "Open Web UI",
            href: local.url
          }, {
            icon: "fa-solid fa-terminal",
            text: "Terminal",
            href: "start.json"
          }]
        } else {
          return [{
            default: true,
            icon: "fa-solid fa-terminal",
            text: "Terminal",
            href: "start.json"
          }]
        }
      } else {
        return [{
          default: true,
          icon: "fa-solid fa-power-off",
          text: "Start",
          href: "start.json"
        }, {
          icon: "fa-solid fa-circle-xmark",
          text: "Reset",
          href: "reset.json"
        }]
      }
    } else {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Install",
        href: "install.json"
      }]
    }
  }
}
